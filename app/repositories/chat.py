from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.db.base import Artifact, ChatSession, Message, utcnow


class ChatRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_session(self, user_id: str, user_metadata: dict[str, object]) -> ChatSession:
        session = ChatSession(user_id=user_id, user_metadata=user_metadata)
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)
        return session

    async def list_sessions(self, user_id: str, limit: int = 30) -> list[ChatSession]:
        result = await self.db.scalars(
            select(ChatSession)
            .where(ChatSession.user_id == user_id)
            .order_by(ChatSession.updated_at.desc())
            .limit(limit)
        )
        return list(result)

    async def require_session(self, session_id: str, user_id: str) -> ChatSession:
        session = await self.db.scalar(
            select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == user_id)
        )
        if session is None:
            raise AppError("session_not_found", "That chat session does not exist.", 404)
        return session

    async def list_messages(self, session_id: str) -> list[Message]:
        result = await self.db.scalars(
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.created_at.asc())
        )
        return list(result)

    async def list_recent_messages(self, session_id: str, limit: int) -> list[Message]:
        if limit <= 0:
            return []
        result = await self.db.scalars(
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        return list(reversed(list(result)))

    async def get_artifacts(self, artifact_ids: list[str]) -> dict[str, Artifact]:
        if not artifact_ids:
            return {}
        result = await self.db.scalars(select(Artifact).where(Artifact.id.in_(artifact_ids)))
        return {item.id: item for item in result}

    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        *,
        mode: str = "answer",
        provider: str | None = None,
        model: str | None = None,
        citations: list[dict[str, object]] | None = None,
        artifact_id: str | None = None,
    ) -> Message:
        message = Message(
            session_id=session_id,
            role=role,
            content=content,
            mode=mode,
            provider=provider,
            model=model,
            citations=citations or [],
            artifact_id=artifact_id,
        )
        self.db.add(message)
        session = await self.db.get(ChatSession, session_id)
        if session:
            session.updated_at = utcnow()
            if not session.title and role == "user":
                session.title = content.strip().replace("\n", " ")[:72]
        await self.db.commit()
        await self.db.refresh(message)
        return message

    async def add_artifact(
        self, session_id: str, kind: str, title: str, source: str, sanitized_html: str
    ) -> Artifact:
        artifact = Artifact(
            session_id=session_id,
            kind=kind,
            title=title,
            source=source,
            sanitized_html=sanitized_html,
        )
        self.db.add(artifact)
        await self.db.flush()
        return artifact
