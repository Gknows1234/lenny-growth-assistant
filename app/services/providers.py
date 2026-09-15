import logging
import os
from dataclasses import dataclass
from typing import Protocol

import httpx

from app.core.config import Settings
from app.core.errors import AppError

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ProviderOutput:
    text: str
    provider: str
    model: str


class LLMProvider(Protocol):
    name: str
    model: str

    async def available(self) -> tuple[bool, str | None]: ...

    async def generate(self, system: str, messages: list[dict[str, str]]) -> ProviderOutput: ...


class OllamaProvider:
    name = "ollama"

    def __init__(self, settings: Settings) -> None:
        self.base_url = settings.ollama_base_url.rstrip("/")
        self.model = settings.ollama_model
        self.timeout = settings.ollama_timeout_seconds

    async def available(self) -> tuple[bool, str | None]:
        try:
            async with httpx.AsyncClient(timeout=min(self.timeout, 3)) as client:
                response = await client.get(f"{self.base_url}/api/tags")
            response.raise_for_status()
            installed = {
                str(item.get("name", ""))
                for item in response.json().get("models", [])
                if isinstance(item, dict)
            }
            aliases = {name.removesuffix(":latest") for name in installed}
            if self.model not in installed and self.model.removesuffix(":latest") not in aliases:
                return False, f"Run: ollama pull {self.model}"
            return True, None
        except Exception:
            return False, "Ollama is not running at the configured URL"

    async def generate(self, system: str, messages: list[dict[str, str]]) -> ProviderOutput:
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, *messages],
            "stream": False,
            "keep_alive": "10m",
            "options": {"num_predict": 4_096, "temperature": 0.2},
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(f"{self.base_url}/api/chat", json=payload)
            if response.status_code == 404:
                raise AppError(
                    "provider_not_configured",
                    f"The Ollama model is not installed. Run: ollama pull {self.model}",
                    503,
                    {"provider": self.name, "model": self.model},
                )
            response.raise_for_status()
            result = response.json().get("message", {}).get("content", "").strip()
            if not result:
                raise ValueError("empty response")
            return ProviderOutput(text=result, provider=self.name, model=self.model)
        except httpx.TimeoutException as exc:
            raise AppError(
                "model_timeout",
                "The local Ollama model took too long to respond. Try a shorter request.",
                504,
                {"provider": self.name, "model": self.model},
            ) from exc
        except AppError:
            raise
        except Exception as exc:
            logger.exception("ollama_generation_failed", extra={"model": self.model})
            raise AppError(
                "provider_unavailable",
                "Ollama could not complete the request. Start Ollama and confirm the model is installed.",
                503,
                {"provider": self.name, "model": self.model},
            ) from exc


class OpenAIProvider:
    name = "openai"

    def __init__(self, settings: Settings) -> None:
        self.api_key = settings.openai_api_key
        self.base_url = settings.openai_base_url.rstrip("/")
        self.model = settings.openai_model
        self.timeout = settings.openai_timeout_seconds

    async def available(self) -> tuple[bool, str | None]:
        if not self.api_key:
            return False, "OPENAI_API_KEY is not configured"
        return True, None

    @staticmethod
    def _output_text(payload: dict[str, object]) -> str:
        parts: list[str] = []
        for item in payload.get("output", []):
            if not isinstance(item, dict) or item.get("type") != "message":
                continue
            for block in item.get("content", []):
                if isinstance(block, dict) and block.get("type") == "output_text":
                    value = block.get("text")
                    if isinstance(value, str):
                        parts.append(value)
        return "\n".join(parts).strip()

    async def generate(self, system: str, messages: list[dict[str, str]]) -> ProviderOutput:
        if not self.api_key:
            raise AppError(
                "provider_not_configured",
                "OpenAI is not configured. Add OPENAI_API_KEY on the server.",
                503,
            )
        payload = {
            "model": self.model,
            "instructions": system,
            "input": messages,
            "max_output_tokens": 4_096,
            "store": False,
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/responses", json=payload, headers=headers
                )
            if response.status_code in {401, 403}:
                raise AppError(
                    "provider_not_configured",
                    "The OpenAI API key is invalid or cannot access the configured model.",
                    503,
                    {"provider": self.name, "model": self.model},
                )
            if response.status_code == 429:
                raise AppError(
                    "provider_rate_limited",
                    "OpenAI is rate limited or the project has insufficient quota. Try again shortly.",
                    429,
                    {"provider": self.name, "model": self.model},
                )
            response.raise_for_status()
            result = self._output_text(response.json())
            if not result:
                raise ValueError("empty response")
            return ProviderOutput(text=result, provider=self.name, model=self.model)
        except httpx.TimeoutException as exc:
            raise AppError(
                "model_timeout",
                "OpenAI took too long to respond. Try a shorter request.",
                504,
                {"provider": self.name, "model": self.model},
            ) from exc
        except AppError:
            raise
        except Exception as exc:
            logger.exception("openai_generation_failed", extra={"model": self.model})
            raise AppError(
                "provider_unavailable",
                "OpenAI could not complete the request. Check the API key, model access, and service status.",
                503,
                {"provider": self.name, "model": self.model},
            ) from exc


class ClaudeAgentSDKProvider:
    name = "claude"

    def __init__(self, settings: Settings) -> None:
        self.api_key = settings.anthropic_api_key
        self.model = settings.claude_model
        self.timeout = settings.claude_timeout_seconds

    async def available(self) -> tuple[bool, str | None]:
        if not self.api_key:
            return False, "ANTHROPIC_API_KEY is not configured"
        return True, None

    async def generate(self, system: str, messages: list[dict[str, str]]) -> ProviderOutput:
        if not self.api_key:
            raise AppError(
                "provider_not_configured",
                "Claude is not configured. Add ANTHROPIC_API_KEY or switch to OpenAI.",
                503,
            )
        try:
            from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, TextBlock, query

            prior = "\n\n".join(f"{item['role'].upper()}: {item['content']}" for item in messages)
            options = ClaudeAgentOptions(
                model=self.model,
                system_prompt=system,
                max_turns=1,
                allowed_tools=[],
                permission_mode="dontAsk",
                env={**os.environ, "ANTHROPIC_API_KEY": self.api_key},
            )
            blocks: list[str] = []
            async for message in query(prompt=prior, options=options):
                if isinstance(message, AssistantMessage):
                    blocks.extend(
                        block.text for block in message.content if isinstance(block, TextBlock)
                    )
            result = "\n".join(blocks).strip()
            if not result:
                raise ValueError("empty response")
            return ProviderOutput(text=result, provider=self.name, model=self.model)
        except AppError:
            raise
        except Exception as exc:
            logger.exception("claude_agent_sdk_failed", extra={"model": self.model})
            raise AppError(
                "provider_unavailable",
                "Claude Agent SDK could not complete the request. Check the API key and service status.",
                503,
                {"provider": self.name, "model": self.model},
            ) from exc


class ProviderRegistry:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.providers: dict[str, LLMProvider] = {
            "ollama": OllamaProvider(settings),
            "openai": OpenAIProvider(settings),
            "claude": ClaudeAgentSDKProvider(settings),
        }

    def get(self, requested: str | None = None) -> LLMProvider:
        name = requested or self.settings.llm_provider
        provider = self.providers.get(name)
        if provider is None:
            raise AppError("unknown_provider", f"Unknown provider: {name}", 400)
        return provider
