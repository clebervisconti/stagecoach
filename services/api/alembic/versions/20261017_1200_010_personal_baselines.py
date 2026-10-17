"""users.personal_baselines JSONB (SPEC §4.7.3)

Revision ID: 010_personal_baselines
Revises: 009_d9_identity
Create Date: 2026-10-17 12:00:00

Reversible. Stores median/MAD per language. Scores stay on population curves.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "010_personal_baselines"
down_revision = "009_d9_identity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("personal_baselines", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "personal_baselines")
