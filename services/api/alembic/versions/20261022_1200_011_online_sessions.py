"""Online session modes, layouts, and review preference.

Revision ID: 011_online_sessions
Revises: 010_personal_baselines
Create Date: 2026-10-22 12:00:00

Reversible. Adds only nullable or defaulted columns (spec §7.1).
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "011_online_sessions"
down_revision = "010_personal_baselines"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sessions",
        sa.Column(
            "delivery_mode",
            sa.String(30),
            nullable=False,
            server_default="stage",
            comment="stage, webinar, online_talk, recorded_video",
        ),
    )
    op.add_column(
        "sessions",
        sa.Column(
            "source_kind",
            sa.String(20),
            nullable=False,
            server_default="upload",
            comment="upload, two_track, url",
        ),
    )
    op.add_column("sessions", sa.Column("source_url", sa.Text(), nullable=True))
    op.add_column("sessions", sa.Column("rights_attested_at", sa.DateTime(), nullable=True))
    op.add_column(
        "sessions",
        sa.Column(
            "analysis_window",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment='{"start_s": float, "end_s": float}',
        ),
    )
    op.add_column(
        "sessions",
        sa.Column(
            "target_length_min",
            sa.Integer(),
            nullable=True,
            comment="recorded_video target length; slot_min stays for live talks",
        ),
    )
    op.create_check_constraint(
        "ck_sessions_delivery_mode",
        "sessions",
        "delivery_mode IN ('stage','webinar','online_talk','recorded_video')",
    )
    op.create_check_constraint(
        "ck_sessions_source_kind",
        "sessions",
        "source_kind IN ('upload','two_track','url')",
    )
    op.create_table(
        "session_layouts",
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
            index=True,
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            comment="detected, auto_confirmed, confirmed, corrected",
        ),
        sa.Column("detector_version", sa.String(20), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("detected", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("confirmed", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("edit_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("job_id", "version", name="uq_session_layouts_job_version"),
    )
    op.add_column(
        "users",
        sa.Column(
            "layout_review_pref",
            sa.String(20),
            nullable=False,
            server_default="when_unsure",
            comment="always, when_unsure, never",
        ),
    )
    op.execute(
        """
        INSERT INTO model_registry (id, component, model_name, version, license, sha)
        VALUES (
            'a7c4e2b1-0d59-5f11-9c2a-3b8e6d1f0470'::uuid,
            'layout_face',
            'face_detection_yunet_2023mar',
            '2023mar',
            'MIT',
            '8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4'
        )
        """
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM model_registry WHERE model_name = 'face_detection_yunet_2023mar'"
    )
    op.drop_column("users", "layout_review_pref")
    op.drop_table("session_layouts")
    op.drop_constraint("ck_sessions_source_kind", "sessions", type_="check")
    op.drop_constraint("ck_sessions_delivery_mode", "sessions", type_="check")
    op.drop_column("sessions", "target_length_min")
    op.drop_column("sessions", "analysis_window")
    op.drop_column("sessions", "rights_attested_at")
    op.drop_column("sessions", "source_url")
    op.drop_column("sessions", "source_kind")
    op.drop_column("sessions", "delivery_mode")
