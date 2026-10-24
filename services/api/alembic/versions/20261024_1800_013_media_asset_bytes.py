"""Widen media_assets.bytes so a 2 GiB recording fits.

Revision ID: 013_media_bytes
Revises: 012_roles_sessions
Create Date: 2026-10-24 18:00:00

PostgreSQL INTEGER tops out at 2147483647. The product limit is 2147483648
(2 GiB), so the old column cannot store a file at the limit. 819 MiB already
fit; this migration is what makes the stated ceiling real.
"""

from alembic import op
import sqlalchemy as sa

revision = "013_media_bytes"
down_revision = "012_roles_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "media_assets",
        "bytes",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "media_assets",
        "bytes",
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=False,
    )
