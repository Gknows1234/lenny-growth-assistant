import re
from dataclasses import dataclass

from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import TranscriptChunk, TranscriptSource

SEARCH_STOPWORDS = {
    "about",
    "and",
    "are",
    "for",
    "from",
    "how",
    "into",
    "is",
    "now",
    "right",
    "should",
    "that",
    "the",
    "these",
    "this",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "with",
    "would",
}


def search_terms(query: str) -> list[str]:
    return [
        term
        for term in dict.fromkeys(re.findall(r"[a-z0-9]{3,}", query.lower()))
        if term not in SEARCH_STOPWORDS
    ][:10]


@dataclass(slots=True)
class SearchHit:
    chunk_id: str
    source_id: str
    title: str
    guest: str
    content: str
    youtube_url: str | None
    start_seconds: int | None
    lexical_score: float


class KnowledgeRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def count_sources(self) -> int:
        return int(await self.db.scalar(select(func.count()).select_from(TranscriptSource)) or 0)

    async def count_chunks(self) -> int:
        return int(await self.db.scalar(select(func.count()).select_from(TranscriptChunk)) or 0)

    async def search(self, query: str, limit: int) -> list[SearchHit]:
        terms = search_terms(query)
        if not terms:
            return []
        bind = self.db.get_bind()
        if bind is not None and bind.dialect.name == "sqlite":
            return await self._search_sqlite(terms, limit)
        websearch_query = " OR ".join(terms)
        statement = text(
            """
            SELECT c.id AS chunk_id, c.source_id, s.title, s.guest, c.content,
                   s.youtube_url, c.start_seconds,
                   ts_rank_cd(c.search_vector, websearch_to_tsquery('english', :query)) AS lexical_score
            FROM transcript_chunks c
            JOIN transcript_sources s ON s.id = c.source_id
            WHERE c.search_vector @@ websearch_to_tsquery('english', :query)
            ORDER BY lexical_score DESC, c.ordinal ASC
            LIMIT :limit
            """
        )
        rows = (
            await self.db.execute(
                statement,
                {"query": websearch_query, "limit": limit},
            )
        ).mappings()
        return [
            SearchHit(
                chunk_id=row["chunk_id"],
                source_id=row["source_id"],
                title=row["title"],
                guest=row["guest"],
                content=row["content"],
                youtube_url=row["youtube_url"],
                start_seconds=row["start_seconds"],
                lexical_score=float(row["lexical_score"] or 0),
            )
            for row in rows
        ]

    async def _search_sqlite(self, terms: list[str], limit: int) -> list[SearchHit]:
        statement = (
            select(TranscriptChunk, TranscriptSource)
            .join(TranscriptSource, TranscriptSource.id == TranscriptChunk.source_id)
            .where(or_(*(func.lower(TranscriptChunk.content).contains(term) for term in terms)))
            .limit(max(limit * 8, 80))
        )
        rows = (await self.db.execute(statement)).all()
        hits: list[SearchHit] = []
        for chunk, source in rows:
            lowered = chunk.content.lower()
            matches = sum(lowered.count(term) for term in terms)
            if not matches:
                continue
            score = matches / max(len(chunk.content) / 1_000, 1)
            hits.append(
                SearchHit(
                    chunk_id=chunk.id,
                    source_id=chunk.source_id,
                    title=source.title,
                    guest=source.guest,
                    content=chunk.content,
                    youtube_url=source.youtube_url,
                    start_seconds=chunk.start_seconds,
                    lexical_score=score,
                )
            )
        hits.sort(key=lambda hit: hit.lexical_score, reverse=True)
        return hits[:limit]
