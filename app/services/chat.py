import logging
import re
import time

from app.core.config import Settings
from app.models.schemas import ArtifactView, Citation, GenerationMode, MessageCreate, MessageView
from app.repositories.chat import ChatRepository
from app.services.artifacts import render_artifact, strip_code_fence
from app.services.prompts import build_context, system_for
from app.services.providers import ProviderRegistry
from app.services.retrieval import Retriever
from app.services.router import route_mode

logger = logging.getLogger(__name__)
CITATION_RE = re.compile(r"\[S(\d+)\]")
ESSAY_MIN_WORDS = 1_100
ESSAY_MAX_WORDS = 1_400
CURRENT_FACT_RE = re.compile(
    r"\b(weather|forecast|temperature|sports? score|stock price|share price|exchange rate|"
    r"current time|latest news)\b",
    re.IGNORECASE,
)
FOLLOW_UP_RE = re.compile(
    r"\b(this|that|these|those|they|them|their|it|guests?|previous|above|"
    r"disagree|compare|next week|do next)\b",
    re.IGNORECASE,
)


def _retrieval_query(content: str, prior_user_messages: list[str]) -> str:
    current = re.sub(r"\s+", " ", content).strip()[:1_600]
    if prior_user_messages and FOLLOW_UP_RE.search(current):
        previous = re.sub(r"\s+", " ", prior_user_messages[-1]).strip()[:1_000]
        # Put the earlier, content-rich question last because retrieval treats
        # trailing terms as the highest-signal focus before relaxing the query.
        return f"{current} {previous}"
    return current


def _ground_citations(text: str, citations: list[Citation]) -> str:
    valid = {citation.id for citation in citations}

    def replace(match: re.Match[str]) -> str:
        marker = f"S{match.group(1)}"
        return match.group(0) if marker in valid else ""

    grounded = CITATION_RE.sub(replace, text).strip()
    if valid and not any(f"[{marker}]" in grounded for marker in valid):
        markers = " ".join(f"[{citation.id}]" for citation in citations[:3])
        grounded = f"{grounded}\n\nSources consulted: {markers}"
    return grounded


def _artifact_title(request: str, mode: GenerationMode) -> str:
    compact = re.sub(r"\s+", " ", request).strip()
    words = compact.split()[:8]
    title = " ".join(words).rstrip(".,?!:;")
    return title[:80] or (
        "Markdown document" if mode == GenerationMode.MARKDOWN else "HTML artifact"
    )


class ChatService:
    def __init__(
        self,
        repository: ChatRepository,
        retriever: Retriever,
        providers: ProviderRegistry,
        settings: Settings,
    ) -> None:
        self.repository = repository
        self.retriever = retriever
        self.providers = providers
        self.settings = settings

    async def respond(
        self, session_id: str, user_id: str, request: MessageCreate
    ) -> tuple[MessageView, str]:
        await self.repository.require_session(session_id, user_id)
        history = await self.repository.list_recent_messages(
            session_id, self.settings.max_history_messages
        )
        mode = route_mode(request.content, request.mode)
        await self.repository.add_message(
            session_id, "user", request.content.strip(), mode=mode.value
        )

        if CURRENT_FACT_RE.search(request.content):
            refusal = (
                "That asks for current information outside Lenny’s Podcast transcripts. "
                "Try a product, growth, leadership, or career question that the transcript library can support."
            )
            saved = await self.repository.add_message(
                session_id, "assistant", refusal, mode=mode.value, citations=[]
            )
            return self._message_view(saved), mode.value

        recent_user_context = [item.content for item in history if item.role == "user"]
        retrieval_query = _retrieval_query(request.content, recent_user_context)
        retrieval_started = time.perf_counter()
        hits = await self.retriever.retrieve(retrieval_query)
        retrieval_ms = round((time.perf_counter() - retrieval_started) * 1_000, 1)
        citations = self.retriever.citations(hits)

        if not hits:
            refusal = (
                "I couldn’t find transcript evidence strong enough to answer that. "
                "Try naming a product topic, company, guest, or framework from Lenny’s Podcast."
            )
            saved = await self.repository.add_message(
                session_id, "assistant", refusal, mode=mode.value, citations=[]
            )
            return self._message_view(saved), mode.value

        provider = self.providers.get(request.provider.value if request.provider else None)

        context = build_context(hits, self.settings.max_context_chars)
        system = f"{system_for(mode)}\n\nREFERENCE PASSAGES\n{context}"
        selected_history: list[object] = []
        history_chars = 0
        for item in reversed(history[-self.settings.max_history_messages :]):
            if history_chars + len(item.content) > self.settings.max_history_chars:
                break
            selected_history.append(item)
            history_chars += len(item.content)
        conversation = [
            {"role": item.role, "content": item.content} for item in reversed(selected_history)
        ]
        conversation.append({"role": "user", "content": request.content.strip()})

        generation_started = time.perf_counter()
        output = await provider.generate(system, conversation)
        if mode == GenerationMode.ESSAY:
            word_count = len(output.text.split())
            if not ESSAY_MIN_WORDS <= word_count <= ESSAY_MAX_WORDS:
                direction = "expand" if word_count < ESSAY_MIN_WORDS else "condense"
                revision = [
                    *conversation,
                    {"role": "assistant", "content": output.text},
                    {
                        "role": "user",
                        "content": (
                            f"Revise this draft to {direction} it into 1,100–1,400 words. "
                            "Return the complete revised essay, preserve only supported claims and valid "
                            "[S#] citations, and keep the hook, parallel headings, and concrete final action."
                        ),
                    },
                ]
                revised = await provider.generate(system, revision)
                revised_count = len(revised.text.split())
                target = 1_250
                if abs(revised_count - target) < abs(word_count - target):
                    output = revised
        generation_ms = round((time.perf_counter() - generation_started) * 1_000, 1)
        grounded = _ground_citations(output.text, citations)
        cited_ids = {f"S{number}" for number in CITATION_RE.findall(grounded)}
        citations = [citation for citation in citations if citation.id in cited_ids]
        artifact_view: ArtifactView | None = None
        artifact_id: str | None = None
        display_content = grounded

        if mode in {GenerationMode.MARKDOWN, GenerationMode.HTML}:
            kind = "markdown" if mode == GenerationMode.MARKDOWN else "html"
            source = strip_code_fence(grounded)
            rendered = render_artifact(kind, source)
            artifact = await self.repository.add_artifact(
                session_id,
                kind,
                _artifact_title(request.content, mode),
                source,
                rendered,
            )
            artifact_id = artifact.id
            artifact_view = ArtifactView(
                id=artifact.id,
                kind=kind,
                title=artifact.title,
                source=artifact.source,
                rendered_html=artifact.sanitized_html,
            )
            display_content = (
                f"Created a {kind.upper()} artifact grounded in {len(citations)} transcript passages. "
                "It’s open in the viewer."
            )

        saved = await self.repository.add_message(
            session_id,
            "assistant",
            display_content,
            mode=mode.value,
            provider=output.provider,
            model=output.model,
            citations=[citation.model_dump() for citation in citations],
            artifact_id=artifact_id,
        )
        logger.info(
            "chat_completed",
            extra={
                "session_id": session_id,
                "mode": mode.value,
                "provider": output.provider,
                "model": output.model,
                "retrieval_hits": len(hits),
                "retrieval_ms": retrieval_ms,
                "generation_ms": generation_ms,
            },
        )
        return self._message_view(saved, artifact_view), mode.value

    @staticmethod
    def _message_view(message: object, artifact: ArtifactView | None = None) -> MessageView:
        return MessageView(
            id=message.id,
            role=message.role,
            content=message.content,
            mode=message.mode,
            provider=message.provider,
            model=message.model,
            citations=[Citation.model_validate(item) for item in message.citations],
            artifact=artifact,
            created_at=message.created_at,
        )
