"""Drills, weekly plan, transcript correction, deck review, and online layout."""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from celery import Celery
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models.analysis_job import AnalysisJob
from app.models.category_score import CategoryScore
from app.models.media_asset import MediaAsset
from app.models.overall_score import OverallScore
from app.models.practice import DrillAttempt, TranscriptRevision
from app.models.session import Session as TalkSession
from app.models.talk_plan import Goal, TalkPlan
from app.models.user import User
from app.quotas import decide_upload, usage_snapshot
from app.quotas import ACTIVE_LIMIT, MONTHLY_LIMIT, STORAGE_LIMIT
from app.readiness import self_serve_readiness

router = APIRouter(tags=["practice"])

MEDIA_ROOT = Path(os.getenv("MEDIA_ROOT", "/data/stagecoach")).resolve()
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
MAX_DRILL_BYTES = 25 * 1024 * 1024


def _practice():
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        candidate = parent / "packages" / "scoring"
        if candidate.exists() and str(candidate) not in sys.path:
            sys.path.insert(0, str(candidate))
            break
    else:
        mounted = Path("/packages/scoring")
        if mounted.exists() and str(mounted) not in sys.path:
            sys.path.insert(0, str(mounted))
    from scoring import practice

    return practice


def _owned_session(session_id: str, user: User, db: Session) -> TalkSession:
    row = (
        db.query(TalkSession)
        .filter(TalkSession.id == session_id, TalkSession.user_id == user.id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return row


class TextAttempt(BaseModel):
    text: str = Field(..., min_length=1, max_length=8000)
    source_session_id: Optional[str] = None
    previous: Optional[float] = None


class TranscriptBody(BaseModel):
    text: str = Field(..., min_length=1, max_length=200000)


class DeckSlides(BaseModel):
    slides: list[dict[str, Any]] = Field(default_factory=list)


@router.get("/account/usage")
def account_usage(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    snap = usage_snapshot(db, current_user)
    return {
        **snap,
        "limits": {
            "storage_bytes": STORAGE_LIMIT,
            "monthly_seconds": MONTHLY_LIMIT,
            "active_jobs": ACTIVE_LIMIT,
        },
    }


@router.get("/account/readiness")
def account_readiness(current_user: User = Depends(get_current_user)) -> dict[str, Any]:
    del current_user
    return self_serve_readiness()


@router.get("/drills")
def get_drills(
    locale: str = Query(default="en"),
    category: Optional[str] = Query(default=None),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    del current_user
    practice = _practice()
    return {"drills": practice.list_drills(locale, category)}


@router.get("/drills/attempts")
def list_attempts(
    drill_id: Optional[str] = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    query = db.query(DrillAttempt).filter(DrillAttempt.user_id == current_user.id)
    if drill_id:
        query = query.filter(DrillAttempt.drill_id == drill_id)
    rows = query.order_by(DrillAttempt.created_at.desc()).limit(30).all()
    return {
        "attempts": [
            {
                "id": str(row.id),
                "drill_id": row.drill_id,
                "status": row.status,
                "result": row.result,
                "source_session_id": str(row.source_session_id) if row.source_session_id else None,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ]
    }


@router.post("/drills/{drill_id}/attempts", status_code=status.HTTP_201_CREATED)
def create_text_attempt(
    drill_id: str,
    body: TextAttempt,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    practice = _practice()
    drill = practice.drill_by_id(drill_id)
    if drill is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown drill")
    if drill_id == "answer_first":
        scored = practice.score_answer(body.text)
    else:
        scored = practice.score_text_drill(drill_id, body.text)
    median = _metric_median(current_user, drill["metrics"][0] if drill["metrics"] else "")
    scored["baseline_sentence"] = practice.baseline_sentence(
        scored.get("metrics", {}).get("words") if isinstance(scored.get("metrics"), dict) else None,
        median,
    )
    if body.previous is not None and isinstance(scored.get("score"), (int, float)):
        scored["delta"] = practice.attempt_delta(float(scored["score"]), body.previous, "higher")
    attempt = DrillAttempt(
        user_id=current_user.id,
        drill_id=drill_id,
        source_session_id=body.source_session_id,
        status="ready",
        result=scored,
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return {"id": str(attempt.id), "status": attempt.status, "result": scored}


@router.post("/drills/{drill_id}/attempts/upload", status_code=status.HTTP_202_ACCEPTED)
async def upload_drill(
    drill_id: str,
    file: UploadFile = File(...),
    source_session_id: Optional[str] = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    practice = _practice()
    drill = practice.drill_by_id(drill_id)
    if drill is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown drill")
    if drill["capture"] == "text":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This drill takes text, not a recording")
    if drill["capture"] == "video":
        from app.consents.store import snapshot_for_user

        grants = snapshot_for_user(db, current_user.id)
        video = (grants.get("purposes") or {}).get("video_analysis") or {}
        if not video.get("granted"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Turn on video analysis before a camera drill.",
            )
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty")
    if len(raw) > MAX_DRILL_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Drill recording is too large")
    decision = decide_upload(db, current_user, incoming_bytes=len(raw), reserved_seconds=int(drill["duration_s"]))
    if not decision["allowed"]:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=decision["reason"])
    attempt = DrillAttempt(
        user_id=current_user.id,
        drill_id=drill_id,
        source_session_id=source_session_id,
        status="queued",
        result={"note": "The recording stays on this machine until scoring finishes."},
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    folder = MEDIA_ROOT / "drills" / str(current_user.id)
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    suffix = Path(file.filename or "take.webm").suffix or ".webm"
    path = folder / f"{attempt.id}{suffix}"
    path.write_bytes(raw)
    path.chmod(0o600)
    attempt.media_uri = str(path)
    db.commit()
    celery = Celery("stagecoach-api", broker=REDIS_URL, backend=REDIS_URL)
    celery.send_task(
        "tasks.score_drill",
        kwargs={
            "attempt_id": str(attempt.id),
            "drill_id": drill_id,
            "media_path": str(path),
            "language": current_user.locale or "en",
        },
        queue="cpu",
    )
    return {"id": str(attempt.id), "status": "queued"}


@router.get("/practice/week")
def practice_week(
    locale: str = Query(default="en"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    practice = _practice()
    categories = _latest_categories(db, current_user.id)
    goals = [
        {
            "id": str(goal.id),
            "metric_id": goal.metric_id,
            "category_id": goal.category_id,
            "target": goal.target,
            "comparator": goal.comparator,
            "achieved_at": goal.achieved_at.isoformat() if goal.achieved_at else None,
        }
        for goal in db.query(Goal).filter(Goal.user_id == current_user.id).all()
    ]
    upcoming = (
        db.query(TalkPlan)
        .filter(TalkPlan.user_id == current_user.id, TalkPlan.talk_date.isnot(None))
        .order_by(TalkPlan.talk_date.asc())
        .first()
    )
    return practice.weekly_plan(
        categories=categories,
        goals=goals,
        talk_date=upcoming.talk_date if upcoming else None,
        locale=locale,
    )


@router.get("/talk-plans/{plan_id}/series")
def talk_series(
    plan_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    plan = (
        db.query(TalkPlan)
        .filter(TalkPlan.id == plan_id, TalkPlan.user_id == current_user.id)
        .first()
    )
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Talk plan not found")
    sessions = (
        db.query(TalkSession)
        .filter(TalkSession.talk_plan_id == plan.id, TalkSession.user_id == current_user.id)
        .order_by(TalkSession.created_at.asc())
        .all()
    )
    rows = []
    for session in sessions:
        job = (
            db.query(AnalysisJob)
            .filter(AnalysisJob.session_id == session.id)
            .order_by(AnalysisJob.created_at.desc())
            .first()
        )
        overall = None
        config_version = None
        categories: dict[str, Any] = {}
        if job is not None:
            config_version = job.scoring_config_version
            score = db.query(OverallScore).filter(OverallScore.job_id == job.id).first()
            if score is not None:
                overall = score.overall
            for cat in db.query(CategoryScore).filter(CategoryScore.job_id == job.id).all():
                categories[cat.category_id] = cat.score
        rows.append(
            {
                "session_id": str(session.id),
                "title": session.title,
                "language": session.language,
                "config_version": config_version,
                "overall": overall,
                "categories": categories,
            }
        )
    practice = _practice()
    return practice.series_compare(rows)


@router.post("/sessions/{session_id}/transcript-correction", status_code=status.HTTP_201_CREATED)
def correct_transcript(
    session_id: str,
    body: TranscriptBody,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    session = _owned_session(session_id, current_user, db)
    practice = _practice()
    signals = practice.transcript_signals(body.text)
    row = TranscriptRevision(
        session_id=session.id,
        user_id=current_user.id,
        body=body.text,
        signals=signals,
    )
    db.add(row)
    db.commit()
    return {"id": str(row.id), "signals": signals}


@router.post("/sessions/{session_id}/deck-review")
async def review_deck(
    session_id: str,
    file: UploadFile | None = File(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Score slide text already attached, or a PPTX sent with this request."""
    session = _owned_session(session_id, current_user, db)
    slides: list[dict[str, str]] = []
    if file is not None:
        name = (file.filename or "").lower()
        data = await file.read()
        if not name.endswith(".pptx"):
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="Deck review reads a .pptx. Download other formats and upload the deck file.",
            )
        from app.deck_text import slide_texts_from_pptx

        slides = slide_texts_from_pptx(data)
    else:
        asset = (
            db.query(MediaAsset)
            .filter(MediaAsset.session_id == session.id, MediaAsset.kind == "deck")
            .order_by(MediaAsset.created_at.desc())
            .first()
        )
        if asset and str(asset.storage_uri).lower().endswith(".pptx"):
            from app.deck_text import slide_texts_from_pptx

            slides = slide_texts_from_pptx(Path(asset.storage_uri).read_bytes())
    practice = _practice()
    return practice.deck_review(slides)


@router.post("/deck-review")
async def review_uploaded_deck(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Score words, density, and assertion headlines from a PPTX. No session required."""
    del current_user
    name = (file.filename or "").lower()
    if not name.endswith(".pptx"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Deck review reads a .pptx. Download other formats and upload the deck file.",
        )
    from app.deck_text import slide_texts_from_pptx

    slides = slide_texts_from_pptx(await file.read())
    return _practice().deck_review(slides)


def _metric_median(user: User, metric_id: str) -> float | None:
    baselines = getattr(user, "personal_baselines", None) or {}
    if not isinstance(baselines, dict):
        return None
    for snapshot in baselines.values():
        if not isinstance(snapshot, dict):
            continue
        metrics = snapshot.get("metrics") or {}
        row = metrics.get(metric_id)
        if isinstance(row, dict) and isinstance(row.get("median"), (int, float)):
            return float(row["median"])
    return None


def _latest_categories(db: Session, user_id: Any) -> list[dict[str, Any]]:
    session = (
        db.query(TalkSession)
        .filter(TalkSession.user_id == user_id)
        .order_by(TalkSession.created_at.desc())
        .first()
    )
    if session is None:
        return []
    job = (
        db.query(AnalysisJob)
        .filter(AnalysisJob.session_id == session.id)
        .order_by(AnalysisJob.created_at.desc())
        .first()
    )
    if job is None:
        return []
    return [
        {"category_id": row.category_id, "score": row.score, "applicable": bool(row.applicable)}
        for row in db.query(CategoryScore).filter(CategoryScore.job_id == job.id).all()
    ]
