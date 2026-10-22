"""Feature flags for online and recorded session modes (OD-10)."""

from __future__ import annotations

import os
from typing import Optional


def flag_on(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def online_modes_flag() -> bool:
    return flag_on("ONLINE_MODES_ENABLED")


def url_ingest_enabled() -> bool:
    return flag_on("URL_INGEST_ENABLED")


def allowed_online_emails() -> set[str]:
    raw = os.getenv("ONLINE_MODES_ALLOWED_EMAILS", "").strip()
    if not raw:
        fallback = os.getenv("PRIVATE_BETA_EMAIL", "").strip()
        raw = fallback
    return {part.strip().lower() for part in raw.split(",") if part.strip()}


def user_online_modes_enabled(email: Optional[str]) -> bool:
    """Online modes require the env flag and an allowlisted account (OD-10)."""
    if not online_modes_flag():
        return False
    allow = allowed_online_emails()
    if not allow:
        return False
    return (email or "").strip().lower() in allow
