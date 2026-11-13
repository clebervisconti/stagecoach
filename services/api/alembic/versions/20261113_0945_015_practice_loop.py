"""Drill attempts and corrected transcripts.

Revision ID: 015_practice_loop
Revises: 014_screen_flow
Create Date: 2026-11-13 09:45:00

Practice takes and transcript corrections. Session delivery columns stay on
011_online_sessions. Minutes for the quota come from media_assets.duration_s.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "015_practice_loop"
down_revision = "014_screen_flow"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "drill_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("drill_id", sa.String(length=80), nullable=False),
        sa.Column("source_session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="ready"),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("media_uri", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_drill_attempts_user_id", "drill_attempts", ["user_id"])
    op.create_table(
        "transcript_revisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("signals", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_transcript_revisions_session_id", "transcript_revisions", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_transcript_revisions_session_id", table_name="transcript_revisions")
    op.drop_table("transcript_revisions")
    op.drop_index("ix_drill_attempts_user_id", table_name="drill_attempts")
    op.drop_table("drill_attempts")
