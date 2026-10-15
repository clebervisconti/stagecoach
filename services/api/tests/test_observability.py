"""Observability helpers (issue #52). No live vendors, no Sentry SDK."""

import os

os.environ.setdefault("DATABASE_URL", "postgresql://stagecoach@127.0.0.1/stagecoach_test")

from app.observability import (
    error_tracking_status,
    handler_label,
    is_admin_email,
    render_metrics,
    summarize_steps,
)


def test_error_tracking_defaults_to_none():
    status = error_tracking_status("none")
    assert status["choice"] == "none"
    assert status["active"] is False
    assert status["needs_owner_decision"] is False


def test_sentry_choices_are_flagged_not_started():
    saas = error_tracking_status("sentry_saas")
    assert saas["needs_owner_decision"] is True
    assert saas["active"] is False
    hosted = error_tracking_status("sentry_self_hosted")
    assert hosted["needs_owner_decision"] is True
    assert hosted["active"] is False


def test_admin_email_list():
    assert is_admin_email("owner@example.com", "owner@example.com, ops@example.com")
    assert not is_admin_email("user@example.com", "owner@example.com")


def test_handler_label_strips_ids():
    assert handler_label("/api/v1/sessions/11111111-1111-4111-8111-111111111136/report") == (
        "/api/v1/sessions/{id}/report"
    )
    assert handler_label("/metrics") == "/metrics"


def test_summarize_steps_sums_cost_without_payloads():
    summary = summarize_steps(
        [
            {"stage": "asr", "status": "succeeded", "metrics": {"duration_s": 12.5}},
            {
                "stage": "content_llm",
                "status": "succeeded",
                "metrics": {"duration_s": 8.0, "total_cost_usd": 0.04, "tokens": 1200},
            },
        ]
    )
    assert summary["total_cost_usd"] == 0.04
    assert summary["total_duration_s"] == 20.5
    assert summary["llm_cost_known"] is True
    blob = str(summary)
    assert "prompt" not in blob
    assert "transcript" not in blob


def test_metrics_exposition_has_no_email():
    body, content_type = render_metrics()
    text = body.decode()
    assert "text/plain" in content_type
    assert "stagecoach_http_requests_total" in text or "stagecoach_analysis_cost" in text
    assert "@" not in text
