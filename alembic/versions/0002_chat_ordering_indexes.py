"""Add indexes for the two ordered chat read paths.

Revision ID: 0002
Revises: 0001
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_chat_sessions_user_updated",
        "chat_sessions",
        ["user_id", "updated_at"],
    )
    op.create_index(
        "ix_messages_session_created",
        "messages",
        ["session_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_messages_session_created", table_name="messages")
    op.drop_index("ix_chat_sessions_user_updated", table_name="chat_sessions")
