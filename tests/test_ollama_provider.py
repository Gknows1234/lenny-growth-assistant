import httpx
import respx

from app.core.config import Settings
from app.services.providers import OllamaProvider, ProviderRegistry


@respx.mock
async def test_ollama_availability_checks_installed_model() -> None:
    respx.get("http://ollama.test/api/tags").mock(
        return_value=httpx.Response(200, json={"models": [{"name": "qwen3:4b-instruct"}]})
    )
    provider = OllamaProvider(
        Settings(ollama_base_url="http://ollama.test", ollama_model="qwen3:4b-instruct")
    )

    available, reason = await provider.available()

    assert available is True
    assert reason is None


@respx.mock
async def test_ollama_chat_is_local_and_non_streaming() -> None:
    route = respx.post("http://ollama.test/api/chat").mock(
        return_value=httpx.Response(
            200,
            json={"message": {"role": "assistant", "content": "Grounded answer [S1]."}},
        )
    )
    provider = OllamaProvider(
        Settings(ollama_base_url="http://ollama.test", ollama_model="qwen3:4b-instruct")
    )

    output = await provider.generate(
        "Use only the references.", [{"role": "user", "content": "What works?"}]
    )

    assert output.text == "Grounded answer [S1]."
    assert output.provider == "ollama"
    assert output.model == "qwen3:4b-instruct"
    request = route.calls[0].request
    assert b'"stream":false' in request.content
    assert b'"role":"system"' in request.content


def test_ollama_is_the_code_default_provider() -> None:
    settings = Settings(_env_file=None)

    assert settings.llm_provider == "ollama"
    assert ProviderRegistry(settings).get().name == "ollama"
