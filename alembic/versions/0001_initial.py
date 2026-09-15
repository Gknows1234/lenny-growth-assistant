"""Initial application and transcript schema.

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chat_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("title", sa.String(140)),
        sa.Column("user_id", sa.String(120), nullable=False),
        sa.Column("user_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_chat_sessions_user_id", "chat_sessions", ["user_id"])

    op.create_table(
        "artifacts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(36),
            sa.ForeignKey("chat_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("title", sa.String(180), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("sanitized_html", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_artifacts_session_id", "artifacts", ["session_id"])

    op.create_table(
        "messages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(36),
            sa.ForeignKey("chat_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("mode", sa.String(20), nullable=False),
        sa.Column("provider", sa.String(30)),
        sa.Column("model", sa.String(100)),
        sa.Column("citations", sa.JSON(), nullable=False),
        sa.Column("artifact_id", sa.String(36), sa.ForeignKey("artifacts.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_messages_session_id", "messages", ["session_id"])

    op.create_table(
        "transcript_sources",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("guest", sa.String(300), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("youtube_url", sa.String(500)),
        sa.Column("publish_date", sa.String(30)),
        sa.Column("source_path", sa.String(600), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("source_metadata", sa.JSON(), nullable=False),
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "transcript_chunks",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column(
            "source_id",
            sa.String(64),
            sa.ForeignKey("transcript_sources.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("start_seconds", sa.Integer()),
    )
    op.create_index("ix_transcript_chunks_source_id", "transcript_chunks", ["source_id"])
    op.execute(
        "ALTER TABLE transcript_chunks ADD COLUMN search_vector tsvector "
        "GENERATED ALWAYS AS (to_tsvector('english', coalesce(content, ''))) STORED"
    )
    op.execute(
        "CREATE INDEX ix_transcript_chunks_search_vector ON transcript_chunks "
        "USING GIN (search_vector)"
    )
    op.create_index(
        "uq_transcript_chunks_source_ordinal",
        "transcript_chunks",
        ["source_id", "ordinal"],
        unique=True,
    )

    op.create_table(
        "ingestion_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("source_ref", sa.String(300), nullable=False),
        sa.Column("sources_seen", sa.Integer(), nullable=False),
        sa.Column("chunks_written", sa.Integer(), nullable=False),
        sa.Column("error", sa.Text()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    op.drop_table("ingestion_runs")
    op.drop_table("transcript_chunks")
    op.drop_table("transcript_sources")
    op.drop_table("messages")
    op.drop_table("artifacts")
    op.drop_table("chat_sessions")
