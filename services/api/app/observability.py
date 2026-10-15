"""OTel traces, Prometheus metrics, and error-tracking gate (issue #52).

No PII, session ids, emails, or transcript text in metric labels.
Sentry SaaS vs self-hosted vs none is an owner decision — default is none.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Iterable

from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Histogram, generate_latest

logger = logging.getLogger(__name__)

ERROR_TRACKING_NONE = "none"
ERROR_TRACKING_SENTRY_SAAS = "sentry_saas"
ERROR_TRACKING_SENTRY_SELF_HOSTED = "sentry_self_hosted"
ERROR_TRACKING_OWNER_CHOICES = (
    ERROR_TRACKING_NONE,
    ERROR_TRACKING_SENTRY_SAAS,
    ERROR_TRACKING_SENTRY_SELF_HOSTED,
)

REGISTRY = CollectorRegistry()
HTTP_REQUESTS = Counter(
    "stagecoach_http_requests_total",
    "HTTP requests (handler template only; no raw paths)",
    ["method", "handler", "code"],
    registry=REGISTRY,
)
STAGE_DURATION = Histogram(
    "stagecoach_stage_duration_seconds",
    "Recorded analysis stage durations",
    ["stage"],
    registry=REGISTRY,
)
ANALYSIS_COST = Counter(
    "stagecoach_analysis_cost_usd_total",
    "Sum of recorded analysis USD costs (no vendor payloads)",
    registry=REGISTRY,
)


def error_tracking_status(raw: str | None = None) -> dict[str, Any]:
    choice = (raw if raw is not None else os.getenv("STAGECOACH_ERROR_TRACKING", ERROR_TRACKING_NONE)).strip() or ERROR_TRACKING_NONE
    if choice not in ERROR_TRACKING_OWNER_CHOICES:
        choice = ERROR_TRACKING_NONE
    pending = choice != ERROR_TRACKING_NONE
    return {
        "choice": choice,
        "active": False,
        "needs_owner_decision": pending,
        "detail": (
            "Owner must choose Sentry SaaS, self-hosted Sentry, or none. "
            "No Sentry SDK is initialized until that decision."
            if pending
            else "Error tracking is off (none). Sentry is not bundled."
        ),
    }


def admin_emails(raw: str | None = None) -> set[str]:
    text = raw if raw is not None else os.getenv("STAGECOACH_ADMIN_EMAILS", "")
    return {part.strip().lower() for part in text.split(",") if part.strip()}


def is_admin_email(email: str | None, raw: str | None = None) -> bool:
    if not email:
        return False
    return email.strip().lower() in admin_emails(raw)


def handler_label(path: str) -> str:
    if path in {"/health", "/ready", "/metrics"}:
        return path
    parts = [part if not _looks_id(part) else "{id}" for part in path.split("/") if part]
    return "/" + "/".join(parts[:6])


def _looks_id(part: str) -> bool:
    if len(part) >= 8 and all(ch in "0123456789abcdef-" for ch in part.lower()):
        return True
    return part.replace(".", "").isdigit()


def observe_request(method: str, path: str, status_code: int) -> None:
    HTTP_REQUESTS.labels(method=method, handler=handler_label(path), code=str(status_code)).inc()


def summarize_steps(steps: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Build a per-analysis cost view from job_steps rows. No prompt/media text."""
    stages: list[dict[str, Any]] = []
    total_cost = 0.0
    total_duration = 0.0
    for step in steps:
        metrics = step.get("metrics") or {}
        if not isinstance(metrics, dict):
            metrics = {}
        duration = _number(metrics.get("duration_s"))
        cost = _number(metrics.get("cost_usd") or metrics.get("total_cost_usd"))
        tokens = _number(metrics.get("tokens") or metrics.get("tokens_used"))
        stage = str(step.get("stage") or "unknown")
        if duration:
            STAGE_DURATION.labels(stage=stage).observe(duration)
        if cost:
            ANALYSIS_COST.inc(cost)
        total_cost += cost
        total_duration += duration
        stages.append(
            {
                "stage": stage,
                "status": step.get("status"),
                "duration_s": duration or None,
                "cost_usd": cost or None,
                "tokens": tokens or None,
            }
        )
    return {
        "stages": stages,
        "total_cost_usd": round(total_cost, 6),
        "total_duration_s": round(total_duration, 3),
        "llm_cost_known": any(row["cost_usd"] for row in stages),
    }


def render_metrics() -> tuple[bytes, str]:
    return generate_latest(REGISTRY), CONTENT_TYPE_LATEST


def init_api_otel() -> bool:
    if not os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
        return False
    try:
        from splunk_otel import init_splunk_otel
    except ImportError:
        return False
    try:
        init_splunk_otel()
        return True
    except Exception:
        logger.exception("OpenTelemetry failed to start")
        return False


class MetricsMiddleware:
    """Count HTTP requests without recording raw URLs."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        status_box = {"code": 500}

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status_box["code"] = message["status"]
            await send(message)

        await self.app(scope, receive, send_wrapper)
        observe_request(scope.get("method", "GET"), scope.get("path", "/"), status_box["code"])


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0
