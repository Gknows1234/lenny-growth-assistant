from urllib.parse import urlparse

from app.core.config import Settings
from app.models.schemas import Citation
from app.repositories.knowledge import KnowledgeRepository, SearchHit


class Retriever:
    def __init__(
        self,
        repository: KnowledgeRepository,
        settings: Settings,
    ) -> None:
        self.repository = repository
        self.settings = settings

    async def retrieve(self, query: str) -> list[SearchHit]:
        hits = await self.repository.search(query, self.settings.retrieval_candidates)
        selected: list[SearchHit] = []
        per_source: dict[str, int] = {}
        for hit in hits:
            if per_source.get(hit.source_id, 0) >= 2:
                continue
            selected.append(hit)
            per_source[hit.source_id] = per_source.get(hit.source_id, 0) + 1
            if len(selected) == self.settings.retrieval_limit:
                break
        return selected

    @staticmethod
    def citations(hits: list[SearchHit]) -> list[Citation]:
        citations: list[Citation] = []
        for index, hit in enumerate(hits, start=1):
            url = hit.youtube_url
            parsed = urlparse(url) if url else None
            if parsed and (
                parsed.scheme != "https"
                or (parsed.hostname or "").lower()
                not in {"youtube.com", "www.youtube.com", "youtu.be", "m.youtube.com"}
            ):
                url = None
            if url and hit.start_seconds is not None:
                separator = "&" if "?" in url else "?"
                url = f"{url}{separator}t={hit.start_seconds}s"
            citations.append(
                Citation(
                    id=f"S{index}",
                    source_id=hit.source_id,
                    title=hit.title,
                    guest=hit.guest,
                    excerpt=hit.content[:360].strip(),
                    url=url,
                    timestamp_seconds=hit.start_seconds,
                    score=round(hit.lexical_score, 4),
                )
            )
        return citations
