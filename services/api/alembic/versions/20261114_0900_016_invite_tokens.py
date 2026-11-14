"""Allow invite rows on auth_tokens before a user exists.

Revision ID: 016_invite_tokens
Revises: 015_practice_loop
Create Date: 2026-11-14 09:00:00

Public registration requires a single-use invite (ADR-093). The invite is
hashed in auth_tokens with no user until it is consumed. No accounts are
inserted.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "016_invite_tokens"
down_revision = "015_practice_loop"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "auth_tokens",
        "user_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=True,
    )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM auth_tokens WHERE user_id IS NULL"))
    op.alter_column(
        "auth_tokens",
        "user_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
    )
