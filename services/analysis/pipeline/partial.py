"""Partial results and graceful vision degradation (issue #46, SPEC §7.6, §6.10).

SSE event shapes match SPEC §7.6. Vision failure does not invent body scores:
categories 12–14 stay N/A with an explicit reason.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

VISION_STATUS_NAME = "vision_status.json"

VISION_FAILED_NA = {
    "gestures_body": "Vision stage failed; gestures & body is unavailable.",
    "eye_contact": "Vision stage failed; audience-facing time is unavailable.",
    "facial_affect": "Vision stage failed; facial movement signals are unavailable.",
}

VISION_FAILED_WARNING = (
    "Vision stage failed; this report uses audio and text. Categories 12–14 are N/A."
)

BODY_CATEGORIES = tuple(VISION_FAILED_NA.keys())


def utc_timestamp() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def stage_event(
    job_id: str,
    stage: str,
    status: str,
    *,
    session_id: str | None = None,
    pct: float | None = None,
    eta_s: int | None = None,
    message: str | None = None,
) -> dict[str, Any]:
    """SPEC §7.6 `type: stage` progress event."""
    return {
        "type": "stage",
        "session_id": session_id,
        "job_id": job_id,
        "stage": stage,
        "status": status,
        "pct": pct,
        "eta_s": eta_s,
        "message": message,
        "timestamp": utc_timestamp(),
    }


def partial_ready_event(
    job_id: str,
    categories: list[str],
    *,
    session_id: str | None = None,
) -> dict[str, Any]:
    """SPEC §7.6 `type: partial_ready` — report page can render these cards now."""
    return {
        "type": "partial_ready",
        "session_id": session_id,
        "job_id": job_id,
        "categories": list(categories),
        "timestamp": utc_timestamp(),
    }


def done_event(
    job_id: str,
    status: str,
    *,
    session_id: str | None = None,
) -> dict[str, Any]:
    """SPEC §7.6 `type: done`."""
    return {
        "type": "done",
        "session_id": session_id,
        "job_id": job_id,
        "status": status,
        "timestamp": utc_timestamp(),
    }


def scored_category_ids(analysis: dict[str, Any]) -> list[str]:
    """Category ids that have a real score (never invented N/A rows)."""
    out: list[str] = []
    for row in analysis.get("categories") or []:
        if row.get("applicable") and row.get("score") is not None:
            cid = row.get("id")
            if isinstance(cid, str):
                out.append(cid)
    return out


def write_vision_status(output_dir: Path, status: str, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"status": status, **extra}
    path = Path(output_dir) / VISION_STATUS_NAME
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def read_vision_status(output_dir: Path) -> dict[str, Any]:
    path = Path(output_dir) / VISION_STATUS_NAME
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def vision_failed_na_reason(output_dir: Path, category_id: str) -> str | None:
    if read_vision_status(output_dir).get("status") != "failed":
        return None
    return VISION_FAILED_NA.get(category_id)


def vision_failed_warning(output_dir: Path) -> str | None:
    if read_vision_status(output_dir).get("status") == "failed":
        return VISION_FAILED_WARNING
    return None
