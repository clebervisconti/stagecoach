"""Email abstraction (D10: Resend). Console stand-in when the key is unset.

Never logs email bodies or tokens. Tests inject a Resend poster; CI makes
no live calls to api.resend.com.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.email_templates import render_email

logger = logging.getLogger(__name__)

RESEND_URL = "https://api.resend.com/emails"
BACKOFF_S = (0.4, 1.2, 3.0)
RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504}

# Tests inspect this; not a log.
OUTBOX: list[dict[str, Any]] = []

Poster = Callable[[str, dict[str, str], dict[str, Any]], tuple[int, str]]


def resend_api_key() -> str:
    return (os.getenv("RESEND_API_KEY") or "").strip()


def email_from() -> str:
    return (os.getenv("STAGECOACH_EMAIL_FROM") or "").strip()


def resend_configured() -> bool:
    return bool(resend_api_key() and email_from())


def email_provider() -> str:
    explicit = (os.getenv("EMAIL_PROVIDER") or "").strip().lower()
    if explicit in {"console", "dev", "mailpit"}:
        return "console"
    if explicit == "resend" or resend_configured():
        return "resend" if resend_configured() else "console"
    return "console"


def send_email(
    *,
    to: str,
    purpose: str,
    token: str | None = None,
    subject: str | None = None,
    body: str | None = None,
    poster: Poster | None = None,
    sleeper: Callable[[float], None] | None = None,
) -> dict[str, Any]:
    """Send via Resend when configured; otherwise the console stand-in."""
    rendered = render_email(purpose, token=token) if token else None
    text = body or (rendered["text"] if rendered else "")
    html = rendered["html"] if rendered else f"<pre>{text}</pre>"
    subject = subject or (rendered["subject"] if rendered else purpose)
    provider = email_provider()
    record = {
        "to": to,
        "subject": subject,
        "text": text,
        "html": html,
        "body": text,
        "purpose": purpose,
        "provider": provider,
    }
    OUTBOX.append(record)
    # Purpose and provider only — never the recipient body or token.
    logger.info("email queued purpose=%s provider=%s", purpose, provider)

    if provider == "resend":
        send_via_resend(
            to=to,
            subject=subject,
            text=text,
            html=html,
            purpose=purpose,
            poster=poster,
            sleeper=sleeper,
        )
    return record


def send_via_resend(
    *,
    to: str,
    subject: str,
    text: str,
    html: str,
    purpose: str,
    poster: Poster | None = None,
    sleeper: Callable[[float], None] | None = None,
) -> dict[str, Any]:
    if not resend_configured():
        raise RuntimeError("Resend is not configured")
    payload = {
        "from": email_from(),
        "to": [to],
        "subject": subject,
        "text": text,
        "html": html,
    }
    headers = {
        "authorization": f"Bearer {resend_api_key()}",
        "content-type": "application/json",
        "user-agent": "stagecoach-api/0.2",
    }
    post = poster or _http_post
    sleep = sleeper or time.sleep
    last_error: Exception | None = None
    for attempt, delay in enumerate((0.0,) + BACKOFF_S, start=1):
        if delay:
            sleep(delay)
        try:
            status, _raw = post(RESEND_URL, headers, payload)
        except URLError as exc:
            last_error = exc
            logger.warning("resend transport error purpose=%s attempt=%s", purpose, attempt)
            continue
        if 200 <= status < 300:
            logger.info("resend accepted purpose=%s attempt=%s", purpose, attempt)
            return {"status": "sent", "provider": "resend", "attempt": attempt}
        retryable = status in RETRYABLE_STATUS
        logger.warning("resend status=%s purpose=%s attempt=%s retryable=%s", status, purpose, attempt, retryable)
        last_error = RuntimeError(f"Resend HTTP {status}")
        if not retryable:
            raise last_error
    raise last_error or RuntimeError("Resend send failed")


def _http_post(url: str, headers: dict[str, str], payload: dict[str, Any]) -> tuple[int, str]:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urlopen(request, timeout=10) as response:  # noqa: S310 — Resend HTTPS only
            return int(response.status), response.read().decode("utf-8")
    except HTTPError as exc:
        # Drain the body so we do not log it; callers only see the status.
        if exc.fp:
            exc.fp.read()
        return int(exc.code), ""


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
