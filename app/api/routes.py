import asyncio
from uuid import uuid4

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.session import database_ready, get_db
from app.models.schemas import (
    AppConfig,
    ArtifactView,
    ChatResponse,
    HealthResponse,
    MessageCreate,
    MessageView,
    ProviderConfig,
    SessionCreate,
    SessionDetail,
    SessionSummary,
)
from app.repositories.chat import ChatRepository
from app.repositories.knowledge import KnowledgeRepository
from app.services.chat import ChatService
from app.services.providers import ProviderRegistry
from app.services.retrieval import Retriever

router = APIRouter()


def current_user(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> str:
    user_id = request.headers.get(settings.session_user_header)
    return (user_id or "anonymous-local")[:120]


@router.get("/health/live", response_model=HealthResponse, tags=["health"])
async def live() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/health/ready", response_model=HealthResponse, tags=["health"])
async def ready(
    db: AsyncSession = Depends(get_db), settings: Settings = Depends(get_settings)
) -> HealthResponse:
    db_ok = await database_ready()
    registry = ProviderRegistry(settings)
    provider = registry.get()
    provider_ok, provider_reason = await provider.available()
    counts = {"sources": 0, "chunks": 0}
    if db_ok:
        knowledge = KnowledgeRepository(db)
        counts = {
            "sources": await knowledge.count_sources(),
            "chunks": await knowledge.count_chunks(),
        }
    checks = {
        "database": {"ok": db_ok},
        "provider": {
            "ok": provider_ok,
            "name": provider.name,
            "model": provider.model,
            "reason": provider_reason,
        },
        "knowledge_base": {"ok": counts["chunks"] > 0, **counts},
    }
    all_ok = db_ok and provider_ok and counts["chunks"] > 0
    return HealthResponse(status="ok" if all_ok else "degraded", checks=checks)


@router.get("/api/config", response_model=AppConfig, tags=["configuration"])
async def config(
    db: AsyncSession = Depends(get_db), settings: Settings = Depends(get_settings)
) -> AppConfig:
    registry = ProviderRegistry(settings)
    availability = await asyncio.gather(
        *(provider.available() for provider in registry.providers.values())
    )
    providers = [
        ProviderConfig(
            name=provider.name,
            model=provider.model,
            available=result[0],
            reason=result[1],
        )
        for provider, result in zip(registry.providers.values(), availability, strict=True)
    ]
    knowledge = KnowledgeRepository(db)
    return AppConfig(
        active_provider=settings.llm_provider,
        providers=providers,
        retrieval={
            "strategy": "lexical_full_text",
            "result_limit": settings.retrieval_limit,
        },
        knowledge_base={
            "sources": await knowledge.count_sources(),
            "chunks": await knowledge.count_chunks(),
        },
    )


@router.post(
    "/api/sessions",
    response_model=SessionSummary,
    status_code=status.HTTP_201_CREATED,
    tags=["sessions"],
)
async def create_session(
    payload: SessionCreate,
    user_id: str = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> SessionSummary:
    session = await ChatRepository(db).create_session(user_id, payload.user_metadata)
    return SessionSummary.model_validate(session, from_attributes=True)


@router.get("/api/sessions", response_model=list[SessionSummary], tags=["sessions"])
async def list_sessions(
    user_id: str = Depends(current_user), db: AsyncSession = Depends(get_db)
) -> list[SessionSummary]:
    sessions = await ChatRepository(db).list_sessions(user_id)
    return [SessionSummary.model_validate(item, from_attributes=True) for item in sessions]


@router.get("/api/sessions/{session_id}", response_model=SessionDetail, tags=["sessions"])
async def get_session(
    session_id: str,
    user_id: str = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> SessionDetail:
    repository = ChatRepository(db)
    session = await repository.require_session(session_id, user_id)
    messages = await repository.list_messages(session_id)
    artifact_ids = [item.artifact_id for item in messages if item.artifact_id]
    artifacts = await repository.get_artifacts(artifact_ids)
    views: list[MessageView] = []
    for item in messages:
        artifact = artifacts.get(item.artifact_id) if item.artifact_id else None
        artifact_view = (
            ArtifactView(
                id=artifact.id,
                kind=artifact.kind,
                title=artifact.title,
                source=artifact.source,
                rendered_html=artifact.sanitized_html,
            )
            if artifact
            else None
        )
        views.append(ChatService._message_view(item, artifact_view))
    return SessionDetail(
        id=session.id,
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
        messages=views,
    )


@router.post("/api/sessions/{session_id}/messages", response_model=ChatResponse, tags=["messages"])
async def create_message(
    session_id: str,
    payload: MessageCreate,
    request: Request,
    user_id: str = Depends(current_user),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ChatResponse:
    repository = ChatRepository(db)
    knowledge = KnowledgeRepository(db)
    service = ChatService(
        repository,
        Retriever(knowledge, settings),
        ProviderRegistry(settings),
        settings,
    )
    message, _ = await service.respond(session_id, user_id, payload)
    return ChatResponse(
        session_id=session_id,
        message=message,
        trace_id=getattr(request.state, "trace_id", str(uuid4())),
    )
