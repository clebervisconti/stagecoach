"""users.retention_policy

Revision ID: 006_retention_policy
Revises: 005_model_registry
Create Date: 2026-10-14 22:10:00

Issue #50 / SPEC §10.1, §10.3. User-configurable retention:
after_analysis | days_30 | until_delete. Default is 30 days after analysis.
"""

from alembic import op
import sqlalchemy as sa

revision = "006_retention_policy"
down_revision = "005_model_registry"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "retention_policy",
            sa.String(32),
            nullable=False,
            server_default="days_30",
            comment="after_analysis, days_30, until_delete",
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "retention_policy")
