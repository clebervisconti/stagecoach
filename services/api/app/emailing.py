"""Email abstraction (D10 still open). Console / dev stand-in only."""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# Tests inspect this; production email waits on D10.
OUTBOX: list[dict[str, Any]] = []


def email_provider() -> str:
    return (os.getenv("EMAIL_PROVIDER") or "console").strip().lower()


def send_email(*, to: str, subject: str, body: str, purpose: str) -> dict[str, Any]:
    """Send via the configured stand-in. Never calls a paid provider."""
    message = {
        "to": to,
        "subject": subject,
        "body": body,
        "purpose": purpose,
        "provider": email_provider(),
    }
    OUTBOX.append(message)
    logger.info("email stand-in purpose=%s provider=%s", purpose, message["provider"])
    if message["provider"] in {"console", "dev", "mailpit"}:
        print(f"[email:{purpose}] to={to} {subject}\n{body}")
    return message


def last_email(*, purpose: str | None = None, to: str | None = None) -> dict[str, Any] | None:
    for message in reversed(OUTBOX):
        if purpose and message["purpose"] != purpose:
            continue
        if to and message["to"] != to:
            continue
        return message
    return None


def clear_outbox() -> None:
    OUTBOX.clear()
