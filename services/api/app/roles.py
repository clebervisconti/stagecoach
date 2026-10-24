"""Product roles. Authorization reads the user row, never an email list."""

from __future__ import annotations

ROLE_ADMIN = "admin"
ROLE_MEMBER = "member"
ROLE_VIEWER = "viewer"
ROLES = (ROLE_ADMIN, ROLE_MEMBER, ROLE_VIEWER)


def normalize_role(value: str | None, *, default: str = ROLE_MEMBER) -> str:
    role = (value or default).strip().lower()
    if role not in ROLES:
        raise ValueError(f"Unknown role: {value}")
    return role
