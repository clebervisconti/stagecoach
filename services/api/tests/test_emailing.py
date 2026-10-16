"""D10 Resend adapter. No live api.resend.com calls."""

import logging
import os

os.environ.setdefault("DATABASE_URL", "postgresql://stagecoach@127.0.0.1/stagecoach_test")

import pytest
from urllib.error import URLError

from app.email_templates import render_email
from app.emailing import (
    BACKOFF_S,
    clear_outbox,
    email_provider,
    last_email,
    send_email,
    send_via_resend,
)


def test_templates_include_text_and_html_without_leaking_into_logs(caplog):
    verify = render_email("verify_email", token="tok-verify")
    reset = render_email("reset_password", token="tok-reset")
    assert "tok-verify" in verify["text"] and "tok-verify" in verify["html"]
    assert "<html" in verify["html"]
    assert "tok-reset" in reset["text"] and "tok-reset" in reset["html"]
    assert "Reset your Stage Coach password" in reset["subject"]
    with caplog.at_level(logging.INFO):
        clear_outbox()
        send_email(to="a@example.invalid", purpose="verify_email", token="tok-verify")
    joined = " ".join(record.getMessage() for record in caplog.records)
    assert "tok-verify" not in joined
    assert "Verify your Stage Coach" not in joined


def test_console_is_default_without_resend_key(monkeypatch):
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    monkeypatch.delenv("STAGECOACH_EMAIL_FROM", raising=False)
    monkeypatch.delenv("EMAIL_PROVIDER", raising=False)
    assert email_provider() == "console"


def test_resend_sends_text_and_html_through_mock(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_test_not_a_real_key")
    monkeypatch.setenv("STAGECOACH_EMAIL_FROM", "Stage Coach <noreply@cybersphere.com.br>")
    monkeypatch.delenv("EMAIL_PROVIDER", raising=False)
    assert email_provider() == "resend"
    calls: list[tuple[str, dict, dict]] = []

    def poster(url, headers, payload):
        calls.append((url, headers, payload))
        return 200, '{"id":"mock"}'

    clear_outbox()
    send_email(
        to="speaker@example.invalid",
        purpose="reset_password",
        token="tok-reset",
        poster=poster,
        sleeper=lambda _s: None,
    )
    assert len(calls) == 1
    url, headers, payload = calls[0]
    assert url == "https://api.resend.com/emails"
    assert headers["authorization"] == "Bearer re_test_not_a_real_key"
    assert payload["from"] == "Stage Coach <noreply@cybersphere.com.br>"
    assert payload["to"] == ["speaker@example.invalid"]
    assert "tok-reset" in payload["text"]
    assert "tok-reset" in payload["html"]
    assert last_email(purpose="reset_password")["provider"] == "resend"


def test_resend_retries_then_succeeds(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_test_not_a_real_key")
    monkeypatch.setenv("STAGECOACH_EMAIL_FROM", "noreply@cybersphere.com.br")
    sleeps: list[float] = []
    statuses = [503, 429, 200]

    def poster(_url, _headers, _payload):
        return statuses.pop(0), ""

    result = send_via_resend(
        to="a@example.invalid",
        subject="x",
        text="t",
        html="<p>t</p>",
        purpose="verify_email",
        poster=poster,
        sleeper=sleeps.append,
    )
    assert result["status"] == "sent"
    assert result["attempt"] == 3
    assert sleeps == [BACKOFF_S[0], BACKOFF_S[1]]


def test_resend_does_not_retry_client_error(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_test_not_a_real_key")
    monkeypatch.setenv("STAGECOACH_EMAIL_FROM", "noreply@cybersphere.com.br")

    def poster(_url, _headers, _payload):
        return 422, ""

    with pytest.raises(RuntimeError, match="Resend HTTP 422"):
        send_via_resend(
            to="a@example.invalid",
            subject="x",
            text="t",
            html="<p>t</p>",
            purpose="verify_email",
            poster=poster,
            sleeper=lambda _s: None,
        )


def test_resend_retries_transport_error_then_raises(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_test_not_a_real_key")
    monkeypatch.setenv("STAGECOACH_EMAIL_FROM", "noreply@cybersphere.com.br")

    def poster(_url, _headers, _payload):
        raise URLError("mocked down")

    with pytest.raises(URLError):
        send_via_resend(
            to="a@example.invalid",
            subject="x",
            text="t",
            html="<p>t</p>",
            purpose="verify_email",
            poster=poster,
            sleeper=lambda _s: None,
        )
