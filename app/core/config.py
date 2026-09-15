from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "The Lenny Growth Assistant"
    app_env: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    database_url: str = "postgresql+asyncpg://lenny:lenny@localhost:5432/lenny"

    llm_provider: Literal["ollama", "openai", "claude"] = "ollama"
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen3:4b-instruct"
    ollama_timeout_seconds: float = Field(default=180, ge=1, le=600)
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"
    openai_timeout_seconds: float = Field(default=180, ge=1, le=600)
    anthropic_api_key: str | None = None
    claude_model: str = "claude-sonnet-4-6"
    claude_timeout_seconds: float = Field(default=180, ge=1, le=600)

    retrieval_limit: int = Field(default=8, ge=1, le=20)
    retrieval_candidates: int = Field(default=30, ge=5, le=100)
    max_context_chars: int = Field(default=24_000, ge=2_000, le=80_000)
    max_history_messages: int = Field(default=10, ge=0, le=30)
    max_history_chars: int = Field(default=12_000, ge=0, le=40_000)

    transcript_repo: str = "https://github.com/ChatPRD/lennys-podcast-transcripts.git"
    transcript_ref: str = "main"
    ingest_limit: int = Field(default=0, ge=0)
    auto_ingest: bool = True

    allowed_origins: str = "http://localhost:8000"
    session_user_header: str = "X-User-Id"

    @property
    def allowed_origin_list(self) -> list[str]:
        return [item.strip() for item in self.allowed_origins.split(",") if item.strip()]

    @property
    def provider_model(self) -> str:
        if self.llm_provider == "ollama":
            return self.ollama_model
        if self.llm_provider == "openai":
            return self.openai_model
        return self.claude_model


@lru_cache
def get_settings() -> Settings:
    return Settings()
