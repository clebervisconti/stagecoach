"""result tables for fusion/report persistence

Revision ID: 003_result_tables
Revises: 002_dag_status
Create Date: 2026-10-14 03:10:00

Issue #30 / SPEC §7.3: transcripts, metric_values, category_scores,
overall_scores, evidence_items, insights.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "003_result_tables"
down_revision = "002_dag_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "transcripts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("analysis_jobs.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("language", sa.String(10), nullable=False),
        sa.Column("language_prob", sa.Float, nullable=True),
        sa.Column("asr_model", sa.String(128), nullable=True),
        sa.Column("words_uri", sa.String(512), nullable=True),
        sa.Column("mean_word_prob", sa.Float, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "metric_values",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("analysis_jobs.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("metric_id", sa.String(80), nullable=False),
        sa.Column("raw_value", sa.Float, nullable=True),
        sa.Column("unit", sa.String(64), nullable=True),
        sa.Column("score", sa.Float, nullable=True),
        sa.Column("confidence", sa.Float, nullable=True),
        sa.Column("source_key", sa.String(32), nullable=True),
        sa.Column("details", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_metric_values_job_metric", "metric_values", ["job_id", "metric_id"])

    op.create_table(
        "category_scores",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("analysis_jobs.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("category_id", sa.String(40), nullable=False),
        sa.Column("score", sa.Integer, nullable=True),
        sa.Column("level", sa.Integer, nullable=True),
        sa.Column("confidence", sa.Float, nullable=True),
        sa.Column("applicable", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("na_reason", sa.Text, nullable=True),
        sa.Column("weight_used", sa.Float, nullable=True),
        sa.Column("explanation", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_category_scores_job_cat", "category_scores", ["job_id", "category_id"], unique=True)

    op.create_table(
        "overall_scores",
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("analysis_jobs.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("overall", sa.Integer, nullable=True),
        sa.Column("coverage", sa.Float, nullable=True),
        sa.Column("overall_confidence", sa.Float, nullable=True),
        sa.Column("display_band", sa.Integer, nullable=True),
        sa.Column("context_type", sa.String(50), nullable=True),
        sa.Column("config_version", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "evidence_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("analysis_jobs.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("category_id", sa.String(40), nullable=False),
        sa.Column("metric_id", sa.String(80), nullable=True),
        sa.Column("t_start", sa.Float, nullable=False),
        sa.Column("t_end", sa.Float, nullable=False),
        sa.Column("modality", sa.String(20), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("quote", sa.Text, nullable=True),
        sa.Column("measurement", postgresql.JSONB, nullable=True),
        sa.Column("seg_ids", postgresql.ARRAY(sa.Text), nullable=True),
        sa.Column("confidence", sa.Float, nullable=True),
        sa.Column("user_disputed", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("dispute_note", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "insights",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("analysis_jobs.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("rank", sa.Integer, nullable=False),
        sa.Column("category_id", sa.String(40), nullable=True),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("body_md", sa.Text, nullable=True),
        sa.Column("fix_md", sa.Text, nullable=True),
        sa.Column("drill_ids", postgresql.ARRAY(sa.Text), nullable=True),
        sa.Column("evidence_ids", postgresql.ARRAY(sa.Text), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("insights")
    op.drop_table("evidence_items")
    op.drop_table("overall_scores")
    op.drop_table("category_scores")
    op.drop_table("metric_values")
    op.drop_table("transcripts")
