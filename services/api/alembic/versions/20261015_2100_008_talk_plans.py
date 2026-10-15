"""talk_plans, goals, objective_scores + sessions.talk_plan_id FK

Revision ID: 008_talk_plans
Revises: 007_llm_settings
Create Date: 2026-10-15 21:00:00

SPEC §7.3 / §7.5 / issue #55. Reversible.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "008_talk_plans"
down_revision = "007_llm_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "talk_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("context_type", sa.String(50), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("audience", postgresql.JSONB, nullable=True),
        sa.Column("goal", sa.Text, nullable=True),
        sa.Column("slot_min", sa.Integer, nullable=True),
        sa.Column("qa_in_slot", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("qa_min", sa.Integer, nullable=True),
        sa.Column("language", sa.String(10), nullable=False, server_default="en"),
        sa.Column("constraints", postgresql.JSONB, nullable=True),
        sa.Column("deck_asset_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("script_text", sa.Text, nullable=True),
        sa.Column(
            "outputs",
            postgresql.JSONB,
            nullable=True,
            comment="core_message, structure, outline, slide_review, time_budget, "
            "cut_list, rehearsal_plan, objectives[]",
        ),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column(
            "edit_history",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
            comment="Versioned user and regenerate edits; no LLM prompts",
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="queued",
            comment="queued, running, ready, failed",
        ),
        sa.Column("talk_date", sa.Date, nullable=True),
        sa.Column("delivery_format", sa.String(20), nullable=True),
        sa.Column("known_habits", postgresql.JSONB, nullable=True),
        sa.Column("must_include", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "goals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("metric_id", sa.String(80), nullable=True),
        sa.Column("category_id", sa.String(80), nullable=True),
        sa.Column("comparator", sa.String(16), nullable=False),
        sa.Column("target", sa.Float, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("achieved_at", sa.DateTime, nullable=True),
    )

    op.create_table(
        "objective_scores",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("analysis_jobs.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "talk_plan_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("talk_plans.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("objective_id", sa.String(80), nullable=False),
        sa.Column(
            "status",
            sa.String(16),
            nullable=False,
            comment="met, partial, not_met, na",
        ),
        sa.Column("score", sa.Float, nullable=True),
        sa.Column("evidence_ids", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    op.create_foreign_key(
        "fk_sessions_talk_plan_id",
        "sessions",
        "talk_plans",
        ["talk_plan_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_sessions_talk_plan_id", "sessions", type_="foreignkey")
    op.drop_table("objective_scores")
    op.drop_table("goals")
    op.drop_table("talk_plans")
