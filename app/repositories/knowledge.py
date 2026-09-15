import re
from dataclasses import dataclass

from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import TranscriptChunk, TranscriptSource

SEARCH_STOPWORDS = {
    "about",
    "advice",
    "and",
    "are",
    "best",
    "can",
    "could",
    "did",
    "does",
    "for",
    "from",
    "guests",
    "how",
    "improve",
    "into",
    "is",
    "key",
    "lessons",
    "most",
    "please",
    "now",
    "people",
    "really",
    "right",
    "said",
    "say",
    "should",
    "that",
    "the",
    "these",
    "this",
    "useful",
    "ways",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "with",
    "would",
}
SEARCH_SHORT_TERMS = {"ai", "pm", "ui", "ux"}


def search_terms(query: str) -> list[str]:
    terms = [
        term
        for term in dict.fromkeys(re.findall(r"[a-z0-9]+", query.lower()))
        if (len(term) >= 3 or term in SEARCH_SHORT_TERMS) and term not in SEARCH_STOPWORDS
    ]
    return terms[-10:]


def postgres_search_queries(terms: list[str]) -> list[str]:
    focus = terms[-4:]
    return [" & ".join(focus[index:]) for index in range(len(focus))]


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

    async def counts(self) -> tuple[int, int]:
        statement = select(
            select(func.count()).select_from(TranscriptSource).scalar_subquery(),
            select(func.count()).select_from(TranscriptChunk).scalar_subquery(),
        )
        sources, chunks = (await self.db.execute(statement)).one()
        return int(sources or 0), int(chunks or 0)

    async def search(self, query: str, limit: int) -> list[SearchHit]:
        terms = search_terms(query)
        if not terms:
            return []
        bind = self.db.get_bind()
        if bind is not None and bind.dialect.name == "sqlite":
            return await self._search_sqlite(terms, limit)
        return await self._search_postgres(terms, limit)

    async def _search_postgres(self, terms: list[str], limit: int) -> list[SearchHit]:
        statement = text(
            """
            WITH matches AS (
                SELECT c.id AS chunk_id, c.source_id, s.title, s.guest, c.content,
                       s.youtube_url, c.start_seconds, c.ordinal,
                       ts_rank_cd(c.search_vector, to_tsquery('english', :query)) AS lexical_score,
                       row_number() OVER (
                           PARTITION BY c.source_id
                           ORDER BY ts_rank_cd(
                               c.search_vector, to_tsquery('english', :query)
                           ) DESC, c.ordinal ASC
                       ) AS source_rank
                FROM transcript_chunks c
                JOIN transcript_sources s ON s.id = c.source_id
                WHERE c.search_vector @@ to_tsquery('english', :query)
            )
            SELECT chunk_id, source_id, title, guest, content, youtube_url,
                   start_seconds, lexical_score
            FROM matches
            WHERE source_rank <= 2
            ORDER BY lexical_score DESC, ordinal ASC
            LIMIT :limit
            """
        )
        # Start with the four most specific trailing terms and relax one term at a
        # time. This keeps PostgreSQL on the GIN index instead of ranking most of
        # the corpus for a broad OR query, while still recovering sparse queries.
        hits: list[SearchHit] = []
        seen: set[str] = set()
        for query in postgres_search_queries(terms):
            rows = (
                await self.db.execute(
                    statement,
                    {"query": query, "limit": limit * 2},
                )
            ).mappings()
            for row in rows:
                if row["chunk_id"] in seen:
                    continue
                seen.add(row["chunk_id"])
                hits.append(
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
                )
                if len(hits) == limit:
                    break
            if len(hits) == limit:
                break
        return hits

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
