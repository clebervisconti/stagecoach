"""Plain-text and HTML bodies for verification and password-reset (issue #67 / D10)."""

from __future__ import annotations

import html
import os
from typing import Any


def public_app_url() -> str:
    return (os.getenv("STAGECOACH_PUBLIC_URL") or os.getenv("NEXTAUTH_URL") or "https://stagecoach.cybersphere.com.br").rstrip("/")


def render_email(purpose: str, *, token: str) -> dict[str, str]:
    if purpose == "verify_email":
        return _verify(token)
    if purpose == "reset_password":
        return _reset(token)
    raise ValueError(f"Unknown email purpose: {purpose}")


def _verify(token: str) -> dict[str, str]:
    safe = html.escape(token)
    link = f"{public_app_url()}/sign-in"
    text = (
        "Verify your Stage Coach email\n\n"
        f"Use this verification token on {link}:\n\n"
        f"{token}\n\n"
        "If you did not create an account, ignore this email."
    )
    body = (
        "<p>Verify your Stage Coach email.</p>"
        f"<p>Open <a href=\"{html.escape(link)}\">{html.escape(link)}</a> "
        f"and enter this token:</p>"
        f"<p><code>{safe}</code></p>"
        "<p>If you did not create an account, ignore this email.</p>"
    )
    return {"subject": "Verify your Stage Coach email", "text": text, "html": _wrap("Verify your email", body)}


def _reset(token: str) -> dict[str, str]:
    safe = html.escape(token)
    link = f"{public_app_url()}/sign-in"
    text = (
        "Reset your Stage Coach password\n\n"
        f"Use this reset token on {link}:\n\n"
        f"{token}\n\n"
        "If you did not ask for a reset, ignore this email."
    )
    body = (
        "<p>Reset your Stage Coach password.</p>"
        f"<p>Open <a href=\"{html.escape(link)}\">{html.escape(link)}</a> "
        f"and enter this token:</p>"
        f"<p><code>{safe}</code></p>"
        "<p>If you did not ask for a reset, ignore this email.</p>"
    )
    return {"subject": "Reset your Stage Coach password", "text": text, "html": _wrap("Reset your password", body)}


def _wrap(title: str, inner: str) -> str:
    return (
        "<!DOCTYPE html><html><head><meta charset=\"utf-8\">"
        f"<title>{html.escape(title)}</title></head>"
        "<body style=\"font-family:sans-serif;line-height:1.5\">"
        f"{inner}</body></html>"
    )


def template_preview(purpose: str) -> dict[str, Any]:
    """Used by tests. Does not send."""
    return render_email(purpose, token="preview-token")
