from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.repositories.chat import ChatRepository


async def test_session_message_and_artifact_round_trip() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as db:
        repository = ChatRepository(db)
        chat = await repository.create_session("evaluator", {"team": "growth"})
        await repository.add_message(chat.id, "user", "How should we grow?")
        artifact = await repository.add_artifact(
            chat.id, "markdown", "Growth brief", "# Brief", "<h1>Brief</h1>"
        )
        await repository.add_message(
            chat.id,
            "assistant",
            "Created the brief.",
            provider="openai",
            model="test-model",
            artifact_id=artifact.id,
        )
        messages = await repository.list_messages(chat.id)
        recent = await repository.list_recent_messages(chat.id, 1)
        artifacts = await repository.get_artifacts([artifact.id])

    assert chat.title == "How should we grow?"
    assert [item.role for item in messages] == ["user", "assistant"]
    assert [item.role for item in recent] == ["assistant"]
    assert artifacts[artifact.id].source == "# Brief"
    await engine.dispose()
