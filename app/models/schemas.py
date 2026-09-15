import json
from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class GenerationMode(StrEnum):
    AUTO = "auto"
    ANSWER = "answer"
    ESSAY = "essay"
    MARKDOWN = "markdown"
    HTML = "html"


class ProviderName(StrEnum):
    OLLAMA = "ollama"
    OPENAI = "openai"
    CLAUDE = "claude"


class SessionCreate(BaseModel):
    user_metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("user_metadata")
    @classmethod
    def metadata_is_small(cls, value: dict[str, Any]) -> dict[str, Any]:
        if len(value) > 32 or len(json.dumps(value, default=str)) > 4_096:
            raise ValueError("user_metadata must be at most 32 fields and 4096 bytes")
        return value


class SessionSummary(BaseModel):
    id: str
    title: str | None
    created_at: datetime
    updated_at: datetime


class Citation(BaseModel):
    id: str
    source_id: str
    title: str
    guest: str
    excerpt: str
    url: str | None = None
    timestamp_seconds: int | None = None
    score: float = 0


class ArtifactView(BaseModel):
    id: str
    kind: Literal["markdown", "html"]
    title: str
    source: str
    rendered_html: str


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=10_000)
    mode: GenerationMode = GenerationMode.AUTO
    provider: ProviderName | None = None


class MessageView(BaseModel):
    id: str
    role: Literal["user", "assistant"]
    content: str
    mode: str
    provider: str | None
    model: str | None
    citations: list[Citation] = Field(default_factory=list)
    artifact: ArtifactView | None = None
    created_at: datetime


class SessionDetail(SessionSummary):
    messages: list[MessageView]


class ChatResponse(BaseModel):
    session_id: str
    message: MessageView
    trace_id: str


class ProviderConfig(BaseModel):
    name: str
    model: str
    available: bool
    reason: str | None = None


class AppConfig(BaseModel):
    active_provider: str
    providers: list[ProviderConfig]
    retrieval: dict[str, Any]
    knowledge_base: dict[str, Any]


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded", "unavailable"]
    checks: dict[str, Any] = Field(default_factory=dict)
