from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base, TranscriptChunk, TranscriptSource
from app.repositories.knowledge import KnowledgeRepository


async def test_sqlite_development_search_returns_ranked_transcript_hits() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as db:
        db.add_all(
            [
                TranscriptSource(
                    id="one",
                    guest="Guest One",
                    title="Activation",
                    source_path="episodes/one/transcript.md",
                    content_hash="a" * 64,
                ),
                TranscriptSource(
                    id="two",
                    guest="Guest Two",
                    title="Leadership",
                    source_path="episodes/two/transcript.md",
                    content_hash="b" * 64,
                ),
                TranscriptChunk(
                    id="one-1",
                    source_id="one",
                    ordinal=0,
                    content="Activation improves when the activation moment is clear.",
                ),
                TranscriptChunk(
                    id="two-1",
                    source_id="two",
                    ordinal=0,
                    content="A manager should create clarity for the team.",
                ),
            ]
        )
        await db.commit()
        hits = await KnowledgeRepository(db).search("activation clarity", 10)

    assert [hit.source_id for hit in hits] == ["one", "two"]
    assert hits[0].lexical_score > hits[1].lexical_score
    await engine.dispose()
