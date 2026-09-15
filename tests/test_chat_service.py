from datetime import UTC, datetime
from types import SimpleNamespace

from app.core.config import Settings
from app.models.schemas import Citation, GenerationMode, MessageCreate
from app.repositories.knowledge import SearchHit
from app.services.chat import ChatService, _retrieval_query
from app.services.providers import ProviderOutput


class FakeRepository:
    def __init__(self) -> None:
        self.messages = []

    async def require_session(self, session_id: str, user_id: str) -> object:
        return object()

    async def list_recent_messages(self, session_id: str, limit: int) -> list[object]:
        return list(self.messages[-limit:]) if limit else []

    async def add_message(self, session_id: str, role: str, content: str, **kwargs) -> object:
        message = SimpleNamespace(
            id=f"m{len(self.messages)}",
            role=role,
            content=content,
            mode=kwargs.get("mode", "answer"),
            provider=kwargs.get("provider"),
            model=kwargs.get("model"),
            citations=kwargs.get("citations", []),
            created_at=datetime.now(UTC),
        )
        self.messages.append(message)
        return message


class EmptyRetriever:
    async def retrieve(self, query: str) -> list[object]:
        return []

    def citations(self, hits: list[object]) -> list[object]:
        return []


class ProviderMustNotRun:
    def get(self, requested: str | None = None) -> object:
        raise AssertionError("The model must not run without transcript evidence")


class EvidenceRetriever:
    async def retrieve(self, query: str) -> list[SearchHit]:
        assert "activation" in query
        return [
            SearchHit(
                "chunk",
                "episode",
                "Activation lessons",
                "Guest",
                "Start with the critical user action.",
                None,
                None,
                1.0,
            )
        ]

    def citations(self, hits: list[SearchHit]) -> list[Citation]:
        return [
            Citation(
                id="S1",
                source_id="episode",
                title="Activation lessons",
                guest="Guest",
                excerpt="Start with the critical user action.",
            )
        ]


class SuccessfulProvider:
    name = "openai"
    model = "test-model"

    def __init__(self) -> None:
        self.messages: list[dict[str, str]] = []

    async def available(self) -> tuple[bool, None]:
        return True, None

    async def generate(self, system: str, messages: list[dict[str, str]]) -> ProviderOutput:
        assert "REFERENCE PASSAGES" in system
        self.messages = messages
        return ProviderOutput(
            "Focus on the critical action [S1], not vanity metrics [S99].", self.name, self.model
        )


class SuccessfulRegistry:
    def __init__(self, provider: SuccessfulProvider) -> None:
        self.provider = provider

    def get(self, requested: str | None = None) -> SuccessfulProvider:
        return self.provider


class ShortThenLongProvider(SuccessfulProvider):
    def __init__(self) -> None:
        super().__init__()
        self.calls = 0

    async def generate(self, system: str, messages: list[dict[str, str]]) -> ProviderOutput:
        self.calls += 1
        words = 600 if self.calls == 1 else 1_200
        return ProviderOutput(f"Essay [S1] {'word ' * words}", self.name, self.model)


def test_retrieval_query_uses_context_only_for_followups() -> None:
    previous = ["How should we improve activation and retention?"]

    assert _retrieval_query("Where do these guests disagree?", previous).endswith(previous[0])
    assert _retrieval_query("How do pricing teams run research?", previous) == (
        "How do pricing teams run research?"
    )


async def test_empty_retrieval_returns_grounded_refusal_without_model_call() -> None:
    repository = FakeRepository()
    service = ChatService(repository, EmptyRetriever(), ProviderMustNotRun(), Settings())
    response, mode = await service.respond(
        "session",
        "user",
        MessageCreate(content="What did the guests say about quantum chromodynamics?"),
    )

    assert mode == "answer"
    assert "couldn’t find transcript evidence" in response.content
    assert response.citations == []
    assert [item.role for item in repository.messages] == ["user", "assistant"]


async def test_current_fact_question_refuses_before_retrieval_or_model() -> None:
    repository = FakeRepository()
    service = ChatService(repository, EmptyRetriever(), ProviderMustNotRun(), Settings())

    response, mode = await service.respond(
        "session",
        "user",
        MessageCreate(content="What is the weather in Bengaluru right now?"),
    )

    assert mode == "answer"
    assert "current information outside" in response.content
    assert response.citations == []


async def test_grounded_answer_persists_provider_and_removes_unknown_citations() -> None:
    repository = FakeRepository()
    provider = SuccessfulProvider()
    service = ChatService(
        repository,
        EvidenceRetriever(),
        SuccessfulRegistry(provider),
        Settings(max_history_chars=100),
    )
    response, mode = await service.respond(
        "session",
        "user",
        MessageCreate(content="How do we improve activation?", mode=GenerationMode.ANSWER),
    )

    assert mode == "answer"
    assert "[S1]" in response.content
    assert "[S99]" not in response.content
    assert response.provider == "openai"
    assert response.model == "test-model"
    assert provider.messages[-1]["content"] == "How do we improve activation?"


async def test_short_essay_gets_one_length_correction() -> None:
    repository = FakeRepository()
    provider = ShortThenLongProvider()
    service = ChatService(
        repository,
        EvidenceRetriever(),
        SuccessfulRegistry(provider),
        Settings(),
    )

    response, mode = await service.respond(
        "session",
        "user",
        MessageCreate(content="Write an essay about activation", mode=GenerationMode.ESSAY),
    )

    assert mode == "essay"
    assert provider.calls == 2
    assert 1_100 <= len(response.content.split()) <= 1_400
