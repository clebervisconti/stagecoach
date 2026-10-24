"""Feature flags for online and recorded session modes (OD-10)."""

from __future__ import annotations

import os


def flag_on(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def online_modes_flag() -> bool:
    return flag_on("ONLINE_MODES_ENABLED")


def url_ingest_enabled() -> bool:
    return flag_on("URL_INGEST_ENABLED")


def user_online_modes_enabled(account: object) -> bool:
    """Online modes require the global flag and the per-user flag (ADR-084).

    Email strings and allowlists do not grant access.
    """
    if not online_modes_flag():
        return False
    if account is None or isinstance(account, str):
        return False
    return bool(getattr(account, "online_modes", False))
