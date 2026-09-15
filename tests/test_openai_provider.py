import httpx
import respx

from app.core.config import Settings
from app.services.providers import OpenAIProvider


async def test_openai_provider_reports_missing_key() -> None:
    provider = OpenAIProvider(Settings(openai_api_key=None))

    available, reason = await provider.available()

    assert available is False
    assert reason == "OPENAI_API_KEY is not configured"


@respx.mock
async def test_openai_provider_uses_responses_api_without_storage() -> None:
    route = respx.post("https://api.openai.test/v1/responses").mock(
        return_value=httpx.Response(
            200,
            json={
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": "Grounded answer [S1]."}],
                    }
                ]
            },
        )
    )
    provider = OpenAIProvider(
        Settings(
            openai_api_key="test-key",
            openai_base_url="https://api.openai.test/v1",
            openai_model="gpt-5-mini",
        )
    )

    output = await provider.generate(
        "Use only the references.", [{"role": "user", "content": "What works?"}]
    )

    assert output.text == "Grounded answer [S1]."
    assert output.provider == "openai"
    assert output.model == "gpt-5-mini"
    assert route.calls[0].request.headers["Authorization"] == "Bearer test-key"
    request = route.calls[0].request
    assert b'"store":false' in request.content
