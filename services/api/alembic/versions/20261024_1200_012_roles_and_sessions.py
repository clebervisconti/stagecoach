"""Roles, session version, forced password change, per-user online modes.

Revision ID: 012_roles_sessions
Revises: 011_online_sessions
Create Date: 2026-10-24 12:00:00

No accounts, emails, or passwords are inserted. The first admin is created
at runtime by ``python -m app.bootstrap_admin``.
"""

from alembic import op
import sqlalchemy as sa

revision = "012_roles_sessions"
down_revision = "011_online_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("role", sa.String(length=32), nullable=False, server_default="member"))
    op.add_column(
        "users",
        sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("users", sa.Column("disabled_at", sa.DateTime(), nullable=True))
    op.add_column(
        "users",
        sa.Column("session_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "users",
        sa.Column("online_modes", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    unique_names = {item["name"] for item in inspector.get_unique_constraints("users")}
    indexes = list(inspector.get_indexes("users"))
    if "users_email_key" in unique_names:
        op.drop_constraint("users_email_key", "users", type_="unique")
    for index in indexes:
        name = index.get("name")
        if not name or name == "users_email_key":
            continue
        columns = list(index.get("column_names") or [])
        if index.get("unique") and columns == ["email"]:
            op.drop_index(name, table_name="users")
    op.create_index(
        "uq_users_email_active",
        "users",
        ["email"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_users_email_active", table_name="users")
    op.create_unique_constraint("users_email_key", "users", ["email"])
    op.drop_column("users", "online_modes")
    op.drop_column("users", "session_version")
    op.drop_column("users", "disabled_at")
    op.drop_column("users", "must_change_password")
    op.drop_column("users", "role")
