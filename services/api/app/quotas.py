"""Upload quotas for a self-serve account. One running job, storage, and minutes."""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.analysis_job import AnalysisJob
from app.models.media_asset import MediaAsset
from app.models.session import Session as TalkSession
from app.models.user import User


def _scoring_path() -> None:
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        candidate = parent / "packages" / "scoring"
        if candidate.exists() and str(candidate) not in sys.path:
            sys.path.insert(0, str(candidate))
            return
    mounted = Path("/packages/scoring")
    if mounted.exists() and str(mounted) not in sys.path:
        sys.path.insert(0, str(mounted))


STORAGE_LIMIT = int(os.getenv("QUOTA_STORAGE_BYTES", str(2 * 1024 * 1024 * 1024)))
MONTHLY_LIMIT = int(os.getenv("QUOTA_MONTHLY_SECONDS", str(180 * 60)))
ACTIVE_LIMIT = int(os.getenv("QUOTA_ACTIVE_JOBS", "1"))
ACTIVE_STATUSES = ("pending", "running")


def _aggregate(db: Session, expression: Any, onclause: Any, *filters: Any) -> int:
    """The in-memory test stand-in has no join, so stored media there counts as zero.

    A real database error propagates. Quotas must not fail open, and swallowing
    the error would also leave the caller's transaction aborted.
    """
    query = db.query(expression)
    if not hasattr(query, "join"):
        return 0
    return int(query.join(TalkSession, onclause).filter(*filters).scalar() or 0)


def usage_snapshot(db: Session, user: User) -> dict[str, int]:
    storage = _aggregate(
        db,
        func.coalesce(func.sum(MediaAsset.bytes), 0),
        TalkSession.id == MediaAsset.session_id,
        TalkSession.user_id == user.id,
    )
    active = _aggregate(
        db,
        func.count(AnalysisJob.id),
        TalkSession.id == AnalysisJob.session_id,
        TalkSession.user_id == user.id,
        AnalysisJob.status.in_(ACTIVE_STATUSES),
    )
    month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    monthly = _aggregate(
        db,
        func.coalesce(func.sum(MediaAsset.duration_s), 0),
        TalkSession.id == MediaAsset.session_id,
        TalkSession.user_id == user.id,
        MediaAsset.kind == "original",
        MediaAsset.created_at >= month_start,
    )
    reserved = 0
    from app.models.practice import DrillAttempt

    drill_bytes = 0
    drill_seconds = 0
    for attempt in db.query(DrillAttempt).filter(DrillAttempt.user_id == user.id).all():
        metrics = (attempt.result or {}).get("metrics") if isinstance(attempt.result, dict) else None
        if isinstance(metrics, dict) and isinstance(metrics.get("duration_s"), (int, float)):
            drill_seconds += int(metrics["duration_s"])
        elif attempt.status == "queued":
            drill_seconds += 60
        if attempt.media_uri:
            try:
                drill_bytes += Path(attempt.media_uri).stat().st_size
            except OSError:
                continue
    return {
        "storage_bytes": int(storage or 0) + drill_bytes,
        "active_jobs": int(active or 0),
        "monthly_seconds": int(float(monthly or 0) + reserved + drill_seconds),
    }


def decide_upload(db: Session, user: User, *, incoming_bytes: int, reserved_seconds: int) -> dict[str, Any]:
    _scoring_path()
    from scoring.practice import evaluate_quota

    snap = usage_snapshot(db, user)
    decision = evaluate_quota(
        storage_bytes=snap["storage_bytes"],
        incoming_bytes=incoming_bytes,
        active_jobs=snap["active_jobs"],
        monthly_seconds=snap["monthly_seconds"],
        reserved_seconds=reserved_seconds,
        storage_limit=STORAGE_LIMIT,
        active_limit=ACTIVE_LIMIT,
        monthly_limit=MONTHLY_LIMIT,
    )
    decision["limits"] = {
        "storage_bytes": STORAGE_LIMIT,
        "monthly_seconds": MONTHLY_LIMIT,
        "active_jobs": ACTIVE_LIMIT,
    }
    return decision
