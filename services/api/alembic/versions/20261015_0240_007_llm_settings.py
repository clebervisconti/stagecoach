"""users.llm_settings

Revision ID: 007_llm_settings
Revises: 006_retention_policy
Create Date: 2026-10-15 02:40:00

Owner decision 2026-10-14: xAI default plus selectable providers.
JSON holds provider / base_url / model only — never API keys.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "007_llm_settings"
down_revision = "006_retention_policy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "llm_settings",
            postgresql.JSONB,
            nullable=True,
            comment="Chosen LLM provider, optional base_url and model. Never API keys.",
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "llm_settings")
