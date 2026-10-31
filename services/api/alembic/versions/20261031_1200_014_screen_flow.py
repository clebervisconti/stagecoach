"""Screen flow document and segments.

Revision ID: 014_screen_flow
Revises: 013_media_bytes
Create Date: 2026-10-31 12:00:00

The analysis file screen_flow.json stays the source of truth. These tables
exist so export and deletion can see the measurement without reading media.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "014_screen_flow"
down_revision = "013_media_bytes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "screen_flows",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sessions.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("analysis_jobs.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
            index=True,
        ),
        sa.Column("version", sa.String(20), nullable=False),
        sa.Column("delivery_mode", sa.String(30), nullable=False),
        sa.Column("screen_visible_s", sa.Float(), nullable=False, server_default="0"),
        sa.Column("segment_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("document", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("content_judgment", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("artifact_uri", sa.String(1024), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "delivery_mode IN ('webinar','online_talk','recorded_video')",
            name="ck_screen_flows_delivery_mode",
        ),
        sa.CheckConstraint("content_judgment = false", name="ck_screen_flows_no_judgment"),
    )
    op.create_table(
        "screen_segments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("analysis_jobs.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sessions.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("index", sa.Integer(), nullable=False),
        sa.Column("t_start", sa.Float(), nullable=False),
        sa.Column("t_end", sa.Float(), nullable=False),
        sa.Column("dwell_s", sa.Float(), nullable=False),
        sa.Column("segment_type", sa.String(16), nullable=False),
        sa.Column("keyframe", sa.String(1024), nullable=True),
        sa.Column("ocr_word_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("deck_page", sa.Integer(), nullable=True),
        sa.Column("activity", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("transition_in", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("narration", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("flags", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("job_id", "index", name="uq_screen_segments_job_index"),
        sa.CheckConstraint(
            "segment_type IN ('SLIDE','DEMO','VIDEO','IDLE')",
            name="ck_screen_segments_type",
        ),
    )


def downgrade() -> None:
    op.drop_table("screen_segments")
    op.drop_table("screen_flows")
