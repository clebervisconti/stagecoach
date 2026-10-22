"""Session, upload, report, playback, and deletion endpoints."""

import hashlib
import hmac
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session
from celery import Celery

from app.account_export import EXPORT_TTL_S, verify_export_link
from app.auth import get_current_user, get_optional_user
from app.auth import jwt as auth_jwt
from app.database import get_db
from app.deletion import (
    assert_no_content,
    audit_details,
    build_object_store,
    count_files,
    delete_local_prefix,
    ip_hash,
    local_session_dir,
    session_object_prefix,
)
from app.coaching import coaching_document, remember_baseline
from app.consents.store import snapshot_for_user
from app.session_plans import resolve_talk_plan
from app.deck_safety import (
    ALLOWED_DECK_CONTENT_TYPES,
    ALLOWED_DECK_EXTENSIONS,
    MAX_DECK_BYTES,
    DeckRejected,
    scan_deck_bytes,
)
from app.models.analysis_job import AnalysisJob
from app.models.audit_log import AuditLog
from app.models.category_score import CategoryScore
from app.models.deletion_request import DeletionRequest
from app.models.evidence_item import EvidenceItem
from app.models.insight import Insight
from app.models.job_step import JobStep
from app.models.user import User
from app.models.session import Session as SessionModel
from app.models.session_layout import SessionLayout
from app.online_flags import online_modes_flag, url_ingest_enabled, user_online_modes_enabled
from app.models.media_asset import MediaAsset
from app.models.metric_value import MetricValue
from app.models.talk_plan import ObjectiveScore, TalkPlan
from app.models.overall_score import OverallScore
from app.models.transcript import Transcript
from app.retention import (
    UNTIL_DELETE,
    retention_until_for,
    normalize_retention_policy,
)

router = APIRouter(prefix="/sessions", tags=["sessions"])

# Configuration
MEDIA_ROOT = Path(os.getenv("MEDIA_ROOT", "/data/stagecoach")).resolve()
MAX_FILE_SIZE = int(os.getenv("MAX_UPLOAD_BYTES", str(2 * 1024 * 1024 * 1024)))
MAX_DURATION_SECONDS = int(os.getenv("MAX_DURATION_SECONDS", str(120 * 60)))
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
ALLOWED_EXTENSIONS = {".mp4", ".mov", ".webm", ".mkv", ".m4a", ".mp3", ".wav", ".ogg", ".flac"}
ALLOWED_CONTENT_TYPES = {
    "video/mp4",
    "video/quicktime",
    "video/webm",
    "video/x-matroska",
    "audio/mp4",
    "audio/mpeg",
    "audio/wav",
    "audio/x-wav",
    "audio/ogg",
    "audio/flac",
    "application/octet-stream",
}
PLAYBACK_TTL_S = 15 * 60
SERIES_NAMES = {
    "pace",
    "pitch",
    "loudness",
    "energy",
    "gesture",
    "gaze",
    "expressivity",
}
VIDEO_SERIES = {"gesture", "gaze", "expressivity"}
MEDIA_TYPES = {
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
    ".webm": "video/webm",
    ".mkv": "video/x-matroska",
    ".m4a": "audio/mp4",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".ogg": "audio/ogg",
    ".flac": "audio/flac",
}


def online_modes_enabled() -> bool:
    return online_modes_flag()


class AnalysisWindow(BaseModel):
    start_s: float
    end_s: float

    @model_validator(mode="after")
    def _ordered(self) -> "AnalysisWindow":
        if self.end_s <= self.start_s:
            raise ValueError("analysis_window end_s must be greater than start_s")
        if self.start_s < 0:
            raise ValueError("analysis_window start_s must be >= 0")
        if self.end_s - self.start_s < 60:
            raise ValueError("analysis_window must be at least 60 seconds")
        return self


class SessionCreate(BaseModel):
    """Session creation request."""
    title: str = Field(..., max_length=255)
    context_type: str = Field(
        ...,
        pattern="^(keynote|breakout|exec_briefing|sales_pitch|virtual_meeting|class_academic|other)$"
    )
    language: str = Field(..., pattern="^(en|pt-BR|auto)$")
    slot_min: Optional[int] = Field(None, ge=1, le=180)
    qa_in_slot: bool = False
    audience_desc: Optional[str] = None
    camera_setup: Optional[str] = Field(
        None,
        pattern="^(stage|to_camera|screen_recording|audio_only|unknown)$",
    )
    talk_plan_id: Optional[UUID] = None
    delivery_mode: str = Field(
        "stage",
        pattern="^(stage|webinar|online_talk|recorded_video)$",
    )
    source_kind: str = Field("upload", pattern="^(upload|two_track|url)$")
    source_url: Optional[str] = None
    rights_attested: bool = False
    analysis_window: Optional[AnalysisWindow] = None
    target_length_min: Optional[int] = Field(None, ge=1, le=180)
    other_people_appear: bool = False

    @model_validator(mode="after")
    def _mode_defaults(self) -> "SessionCreate":
        if not self.camera_setup:
            if self.delivery_mode == "stage":
                raise ValueError("camera_setup is required when delivery_mode is stage")
            self.camera_setup = "unknown"
        if self.target_length_min is not None and self.delivery_mode != "recorded_video":
            raise ValueError("target_length_min is only accepted for recorded_video")
        return self


def gate_online_session_fields(session_data: SessionCreate, email: Optional[str] = None) -> None:
    """Reject online-only fields unless the flag is on for this account (OD-10)."""
    onlineish = (
        session_data.delivery_mode != "stage"
        or session_data.source_kind != "upload"
        or session_data.source_url is not None
        or session_data.analysis_window is not None
        or session_data.target_length_min is not None
    )
    if onlineish and not user_online_modes_enabled(email):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Online modes are not enabled",
        )
    if session_data.source_kind == "url" and not url_ingest_enabled():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="URL ingest is not enabled",
        )
    needs_rights = (
        session_data.delivery_mode in {"webinar", "online_talk"}
        or session_data.source_kind == "url"
        or (session_data.delivery_mode == "recorded_video" and session_data.other_people_appear)
    )
    if needs_rights and not session_data.rights_attested:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="rights_attested is required",
        )


class SessionResponse(BaseModel):
    """Session response."""
    id: str
    title: str
    status: str
    upload: dict


class PdfExportRequest(BaseModel):
    include_transcript: bool = False


def _owned_session(session_id: str, user: User, db: Session) -> SessionModel:
    session = (
        db.query(SessionModel)
        .filter(SessionModel.id == session_id, SessionModel.user_id == user.id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return session


def _safe_artifact_path(raw_path: str) -> Path:
    candidate = Path(raw_path).resolve()
    if not candidate.is_relative_to(MEDIA_ROOT):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found")
    if not candidate.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found")
    return candidate


def _latest_job(session: SessionModel, db: Session) -> AnalysisJob:
    job = (
        db.query(AnalysisJob)
        .filter(AnalysisJob.session_id == session.id)
        .order_by(AnalysisJob.created_at.desc())
        .first()
    )
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No analysis job")
    return job


def _merged_outputs(job: AnalysisJob, db: Session) -> dict:
    steps = (
        db.query(JobStep)
        .filter(JobStep.job_id == job.id, JobStep.status == "succeeded")
        .order_by(JobStep.created_at.asc())
        .all()
    )
    outputs: dict = {}
    for step in steps:
        if step.output_uris:
            outputs.update(step.output_uris)
    return outputs


def _outputs_or_conflict(session: SessionModel, db: Session) -> tuple[AnalysisJob, dict]:
    job = _latest_job(session, db)
    outputs = _merged_outputs(job, db)
    return job, outputs


def _artifact_from_outputs(outputs: dict, key: str) -> Path:
    raw = outputs.get(key)
    if not raw:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"{key} is not ready")
    return _safe_artifact_path(raw)


def _artifact_dir(outputs: dict) -> Optional[Path]:
    for key in ("report", "analysis_result", "transcript"):
        raw = outputs.get(key)
        if raw:
            return Path(raw).resolve().parent
    return None


def sign_playback(session_id: str, expires_at: int) -> str:
    secret = auth_jwt.AUTH_SECRET
    if len(secret) < 32:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Playback signing is not configured")
    payload = f"{session_id}:{expires_at}".encode()
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


def verify_playback(session_id: str, expires_at: int, signature: str) -> bool:
    if len(auth_jwt.AUTH_SECRET) < 32:
        return False
    expected = sign_playback(session_id, expires_at)
    return hmac.compare_digest(expected, signature or "")


def _highlights_from_artifacts(transcript: dict, report: Optional[dict]) -> list[dict]:
    """Highlights from existing evidence only. Never invents spans."""
    highlights = []
    for item in (report or {}).get("evidence") or []:
        highlights.append(
            {
                "kind": item.get("kind") or "observation",
                "category_id": item.get("category_id"),
                "metric_id": item.get("metric_id"),
                "t_start": item.get("t_start"),
                "t_end": item.get("t_end"),
                "text": item.get("text"),
                "quote": item.get("quote"),
                "user_disputed": bool(item.get("user_disputed")),
            }
        )
    return highlights


def _empty_series(name: str, duration_s: float) -> dict:
    length = max(1, int(duration_s) if duration_s else 1)
    return {
        "name": name,
        "resolution_s": 1,
        "points": [{"t": float(i), "value": None} for i in range(length)],
        "unavailable": True,
        "na_reason": "Vision series are not produced in Phase 1 (audio/text only).",
    }


@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    session_data: SessionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a private-beta session and return the authenticated upload route."""
    gate_online_session_fields(session_data, current_user.email)
    plan = resolve_talk_plan(db, current_user.id, session_data.talk_plan_id)
    attested_at = datetime.now(timezone.utc).replace(tzinfo=None) if session_data.rights_attested else None
    session = SessionModel(
        user_id=current_user.id,
        title=session_data.title,
        context_type=session_data.context_type,
        language=session_data.language,
        slot_min=session_data.slot_min,
        qa_in_slot=session_data.qa_in_slot,
        audience_desc=session_data.audience_desc,
        camera_setup=session_data.camera_setup or "unknown",
        delivery_mode=session_data.delivery_mode,
        source_kind=session_data.source_kind,
        source_url=session_data.source_url,
        rights_attested_at=attested_at,
        analysis_window=session_data.analysis_window.model_dump() if session_data.analysis_window else None,
        target_length_min=session_data.target_length_min,
        talk_plan_id=plan.id if plan is not None else None,
        status="created",
    )
    
    db.add(session)
    db.flush()
    if attested_at is not None:
        db.add(
            AuditLog(
                actor_id=current_user.id,
                action="rights_attested",
                target_type="session",
                target_id=str(session.id),
                at=attested_at,
                details={"attested": True},
            )
        )
    db.commit()
    db.refresh(session)
    
    return SessionResponse(
        id=str(session.id),
        title=session.title,
        status=session.status,
        upload={
            "url": f"/api/v1/sessions/{session.id}/upload",
            "max_size_bytes": MAX_FILE_SIZE,
            "resumable": False,
        }
    )


@router.get("")
async def list_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List user sessions."""
    sessions = db.query(SessionModel).filter(
        SessionModel.user_id == current_user.id
    ).order_by(SessionModel.created_at.desc()).limit(20).all()
    session_ids = [s.id for s in sessions]
    latest_jobs: dict = {}
    if session_ids:
        for job in (
            db.query(AnalysisJob)
            .filter(AnalysisJob.session_id.in_(session_ids))
            .order_by(AnalysisJob.created_at.desc())
            .all()
        ):
            latest_jobs.setdefault(job.session_id, job)
    score_by_job = {}
    job_ids = [job.id for job in latest_jobs.values()]
    if job_ids:
        for row in db.query(OverallScore).filter(OverallScore.job_id.in_(job_ids)).all():
            score_by_job[row.job_id] = row

    return {"sessions": [
        {
            "id": str(s.id),
            "title": s.title,
            "status": s.status,
            "context_type": s.context_type,
            "delivery_mode": getattr(s, "delivery_mode", "stage"),
            "language": s.language,
            "slot_min": s.slot_min,
            "created_at": s.created_at.isoformat(),
            "updated_at": s.updated_at.isoformat(),
            "overall": score_by_job[latest_jobs[s.id].id].overall
            if s.id in latest_jobs and latest_jobs[s.id].id in score_by_job
            else None,
        }
        for s in sessions
    ]}


@router.get("/{session_id}")
async def get_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = _owned_session(session_id, current_user, db)
    job = (
        db.query(AnalysisJob)
        .filter(AnalysisJob.session_id == session.id)
        .order_by(AnalysisJob.created_at.desc())
        .first()
    )
    steps = []
    if job:
        steps = (
            db.query(JobStep)
            .filter(JobStep.job_id == job.id)
            .order_by(JobStep.created_at.asc())
            .all()
        )
    return {
        "id": str(session.id),
        "title": session.title,
        "status": session.status,
        "context_type": session.context_type,
        "delivery_mode": getattr(session, "delivery_mode", "stage"),
        "source_kind": getattr(session, "source_kind", "upload"),
        "language": session.language,
        "slot_min": session.slot_min,
        "qa_in_slot": session.qa_in_slot,
        "camera_setup": session.camera_setup,
        "qa_included": session.qa_in_slot,
        "target_length_min": getattr(session, "target_length_min", None),
        "rights_attested_at": session.rights_attested_at.isoformat()
        if getattr(session, "rights_attested_at", None)
        else None,
        "created_at": session.created_at.isoformat(),
        "job": (
            {
                "id": str(job.id),
                "status": job.status,
                "error": job.error,
                "created_at": job.created_at.isoformat(),
                "steps": [
                    {
                        "stage": step.stage,
                        "status": step.status,
                        "metrics": step.metrics,
                        "message": (
                            step.metrics.get("message") or step.metrics.get("reason")
                            if isinstance(step.metrics, dict)
                            else None
                        ),
                        "error": step.error.get("message")
                        if isinstance(step.error, dict)
                        else None,
                        "started_at": step.started_at.isoformat() if step.started_at else None,
                        "finished_at": step.finished_at.isoformat() if step.finished_at else None,
                    }
                    for step in steps
                ],
            }
            if job
            else None
        ),
    }


def _probe_duration_seconds(path: Path) -> Optional[float]:
    import subprocess

    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "csv=p=0",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        raw = (result.stdout or "").strip()
        return float(raw) if raw else None
    except (subprocess.CalledProcessError, ValueError, FileNotFoundError, subprocess.TimeoutExpired):
        return None


@router.post("/{session_id}/upload", status_code=status.HTTP_202_ACCEPTED)
async def upload_and_analyze(
    session_id: str,
    file: UploadFile = File(...),
    rights_attested: bool = Form(False),
    role: str = Form("primary"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Stream a bounded upload to a generated private path and enqueue analysis."""
    session = _owned_session(session_id, current_user, db)
    if session.status not in {"created", "failed"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Session already uploaded")
    _ = role
    delivery_mode = getattr(session, "delivery_mode", "stage") or "stage"
    if delivery_mode != "stage" and not user_online_modes_enabled(current_user.email):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Online modes are not enabled")
    needs_rights = delivery_mode in {"webinar", "online_talk"}
    if needs_rights and not (rights_attested or session.rights_attested_at):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="rights_attested is required")
    if rights_attested and session.rights_attested_at is None:
        session.rights_attested_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.add(
            AuditLog(
                actor_id=current_user.id,
                action="rights_attested",
                target_type="session",
                target_id=str(session.id),
                at=session.rights_attested_at,
                details={"attested": True},
            )
        )

    original_name = file.filename or ""
    extension = Path(original_name).suffix.casefold()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Unsupported file type")
    if file.content_type and file.content_type.casefold() not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Unsupported content type")

    session_dir = (MEDIA_ROOT / str(session.id)).resolve()
    if not session_dir.is_relative_to(MEDIA_ROOT):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid session path")
    upload_dir = session_dir / "upload"
    upload_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    stored_path = upload_dir / f"{uuid.uuid4().hex}{extension}"

    digest = hashlib.sha256()
    total = 0
    try:
        with stored_path.open("xb") as destination:
            while chunk := await file.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_FILE_SIZE:
                    limit_gb = MAX_FILE_SIZE / (1024 ** 3)
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"This file is larger than {limit_gb:g} GB. Trim it or export at 720p.",
                    )
                digest.update(chunk)
                destination.write(chunk)
        stored_path.chmod(0o600)
    except Exception:
        stored_path.unlink(missing_ok=True)
        raise
    finally:
        await file.close()

    if total == 0:
        stored_path.unlink(missing_ok=True)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty")

    duration = _probe_duration_seconds(stored_path)
    if duration is not None and duration > MAX_DURATION_SECONDS:
        stored_path.unlink(missing_ok=True)
        limit_min = int(MAX_DURATION_SECONDS / 60)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"This recording is longer than {limit_min} minutes.",
        )

    policy = normalize_retention_policy(getattr(current_user, "retention_policy", None))
    retention_until = retention_until_for(policy, datetime.utcnow(), event="upload")
    asset = MediaAsset(
        session_id=session.id,
        kind="original",
        storage_uri=str(stored_path),
        bytes=total,
        sha256=digest.hexdigest(),
        retention_until=retention_until,
        codec_info={"content_type": file.content_type, "extension": extension, "retention_policy": policy},
    )
    job = AnalysisJob(
        session_id=session.id,
        scoring_config_version="1.1.0",
        pipeline_version="0.2.0",
        status="pending",
    )
    session.status = "uploaded"
    db.add(asset)
    db.add(job)
    db.commit()
    db.refresh(job)

    output_dir = session_dir / str(job.id)
    celery = Celery("stagecoach-api", broker=REDIS_URL, backend=REDIS_URL)
    online = delivery_mode != "stage"
    task_name = "tasks.prepare_session" if online else "tasks.run_mvp_analysis"
    kwargs = {
        "job_id": str(job.id),
        "session_id": str(session.id),
        "input_path": str(stored_path),
        "output_dir": str(output_dir),
        "context_type": session.context_type,
        "language": session.language,
        "slot_min": session.slot_min,
        "consents": snapshot_for_user(db, current_user.id),
        "camera_setup": session.camera_setup,
        "accessibility_profile": current_user.accessibility_profile or {},
        "retention_policy": policy,
        "llm_settings": getattr(current_user, "llm_settings", None) or {},
        "qa_in_slot": bool(session.qa_in_slot),
        "audience_desc": session.audience_desc,
    }
    if online:
        kwargs["delivery_mode"] = delivery_mode
        kwargs["source_kind"] = getattr(session, "source_kind", "upload") or "upload"
    celery.send_task(task_name, kwargs=kwargs, queue="cpu")
    session.status = "preparing" if online else "processing"
    db.commit()
    return {"session_id": str(session.id), "job_id": str(job.id), "status": session.status}


@router.post("/{session_id}/deck", status_code=status.HTTP_201_CREATED)
async def attach_deck(
    session_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Attach a PPTX/PDF deck. Worker sandbox repeats the antivirus scan (issue #43)."""
    session = _owned_session(session_id, current_user, db)
    original_name = file.filename or "deck"
    extension = Path(original_name).suffix.casefold()
    if extension not in ALLOWED_DECK_EXTENSIONS:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Deck must be .pptx or .pdf")
    if file.content_type and file.content_type.casefold() not in ALLOWED_DECK_CONTENT_TYPES:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Unsupported deck content type")

    session_dir = (MEDIA_ROOT / str(session.id)).resolve()
    if not session_dir.is_relative_to(MEDIA_ROOT):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid session path")
    session_dir.mkdir(parents=True, exist_ok=True, mode=0o700)

    digest = hashlib.sha256()
    chunks: list[bytes] = []
    total = 0
    try:
        while chunk := await file.read(1024 * 1024):
            total += len(chunk)
            if total > MAX_DECK_BYTES:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="Deck exceeds the 50 MB limit",
                )
            digest.update(chunk)
            chunks.append(chunk)
    finally:
        await file.close()
    data = b"".join(chunks)
    try:
        kind = scan_deck_bytes(data, original_name)
    except DeckRejected as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    stored_path = session_dir / f"deck.{kind}"
    stored_path.write_bytes(data)
    stored_path.chmod(0o600)

    retention_until = retention_until_for(UNTIL_DELETE, datetime.utcnow(), event="upload")
    asset = MediaAsset(
        session_id=session.id,
        kind="deck",
        storage_uri=str(stored_path),
        bytes=total,
        sha256=digest.hexdigest(),
        retention_until=retention_until,
        codec_info={"content_type": file.content_type, "extension": f".{kind}", "filename": original_name},
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return {
        "session_id": str(session.id),
        "deck_asset_id": str(asset.id),
        "kind": kind,
        "bytes": total,
        "sha256": digest.hexdigest(),
    }


@router.get("/{session_id}/report")
async def get_report(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = _owned_session(session_id, current_user, db)
    _, outputs = _outputs_or_conflict(session, db)
    report_path = _artifact_from_outputs(outputs, "report")
    return json.loads(report_path.read_text())


def _coaching_inputs(session: SessionModel, user: User, db: Session) -> dict:
    plan = None
    if session.talk_plan_id:
        plan = (
            db.query(TalkPlan)
            .filter(TalkPlan.id == session.talk_plan_id, TalkPlan.user_id == user.id)
            .first()
        )
    outputs = plan.outputs if plan and isinstance(plan.outputs, dict) else {}
    groups: list[list[dict]] = []
    if plan:
        linked = (
            db.query(SessionModel)
            .filter(SessionModel.talk_plan_id == plan.id, SessionModel.user_id == user.id)
            .order_by(SessionModel.created_at.asc())
            .all()
        )
        for linked_session in linked:
            job_ids = [
                row.id
                for row in db.query(AnalysisJob).filter(AnalysisJob.session_id == linked_session.id).all()
            ]
            if not job_ids:
                continue
            scores = (
                db.query(ObjectiveScore)
                .filter(ObjectiveScore.job_id.in_(job_ids), ObjectiveScore.talk_plan_id == plan.id)
                .all()
            )
            if not scores:
                continue
            groups.append(
                [
                    {"objective_id": row.objective_id, "status": row.status, "score": row.score}
                    for row in scores
                ]
            )
    history_rows = (
        db.query(MetricValue.metric_id, MetricValue.raw_value, SessionModel.id)
        .join(AnalysisJob, MetricValue.job_id == AnalysisJob.id)
        .join(SessionModel, AnalysisJob.session_id == SessionModel.id)
        .filter(
            SessionModel.user_id == user.id,
            SessionModel.language == session.language,
            MetricValue.raw_value.isnot(None),
        )
        .all()
    )
    history: dict[str, list[float]] = {}
    session_ids: set = set()
    for metric_id, raw_value, session_id in history_rows:
        history.setdefault(str(metric_id), []).append(float(raw_value))
        session_ids.add(session_id)
    current_job = (
        db.query(AnalysisJob)
        .filter(AnalysisJob.session_id == session.id)
        .order_by(AnalysisJob.created_at.desc())
        .first()
    )
    current_metrics = []
    if current_job is not None:
        for row in db.query(MetricValue).filter(MetricValue.job_id == current_job.id).all():
            current_metrics.append(
                {"metric_id": row.metric_id, "raw_value": row.raw_value, "score": row.score}
            )
    return coaching_document(
        objectives=list(outputs.get("objectives") or []),
        outline=list(outputs.get("outline") or []),
        rehearsal_groups=groups,
        language=session.language or "en",
        history=history,
        n_sessions=len(session_ids),
        current_metrics=current_metrics,
        linked_plan=plan is not None,
    )


@router.get("/{session_id}/coaching")
async def get_coaching(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = _owned_session(session_id, current_user, db)
    document = _coaching_inputs(session, current_user, db)
    if remember_baseline(current_user, session.language or "en", document["baseline"]):
        db.commit()
    return document


@router.get("/{session_id}/analysis")
async def get_analysis(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = _owned_session(session_id, current_user, db)
    _, outputs = _outputs_or_conflict(session, db)
    raw = outputs.get("analysis_result") or outputs.get("report")
    if not raw:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Analysis is not ready")
    return json.loads(_safe_artifact_path(raw).read_text())


@router.get("/{session_id}/transcript")
async def get_transcript(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = _owned_session(session_id, current_user, db)
    _, outputs = _outputs_or_conflict(session, db)
    transcript_path = _artifact_from_outputs(outputs, "transcript")
    transcript = json.loads(transcript_path.read_text())
    report = None
    raw_report = outputs.get("report") or outputs.get("analysis_result")
    if raw_report:
        try:
            report = json.loads(_safe_artifact_path(raw_report).read_text())
        except HTTPException:
            report = None
    words = []
    for segment in transcript.get("segments") or []:
        if segment.get("words"):
            words.extend(segment["words"])
        else:
            tokens = str(segment.get("text") or "").split()
            start = float(segment.get("start") or 0)
            end = float(segment.get("end") or start)
            step = (end - start) / max(len(tokens), 1)
            for i, token in enumerate(tokens):
                words.append(
                    {
                        "word": token,
                        "start": start + i * step,
                        "end": start + (i + 1) * step,
                        "probability": transcript.get("mean_word_probability")
                        or transcript.get("mean_word_prob"),
                    }
                )
    sidecar = []
    if transcript_path is not None:
        disambig_file = transcript_path.parent / "fluency_disambig.json"
        if disambig_file.is_file():
            try:
                sidecar = json.loads(disambig_file.read_text()).get("disambiguations") or []
            except json.JSONDecodeError:
                sidecar = []
    return {
        "language": transcript.get("language"),
        "duration": transcript.get("duration"),
        "segments": transcript.get("segments") or [],
        "words": words,
        "highlights": _highlights_from_artifacts(transcript, report),
        "disambiguations": sidecar,
    }


@router.get("/{session_id}/series/{name}")
async def get_series(
    session_id: str,
    name: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if name not in SERIES_NAMES:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown series")
    session = _owned_session(session_id, current_user, db)
    _, outputs = _outputs_or_conflict(session, db)
    raw = outputs.get(f"series_{name}")
    if raw:
        return json.loads(_safe_artifact_path(raw).read_text())
    directory = _artifact_dir(outputs)
    if directory:
        candidate = (directory / f"series_{name}.json").resolve()
        if candidate.is_file() and candidate.is_relative_to(MEDIA_ROOT):
            return json.loads(candidate.read_text())
    if name in VIDEO_SERIES:
        duration = 1.0
        raw_report = outputs.get("report") or outputs.get("analysis_result")
        if raw_report:
            try:
                report = json.loads(_safe_artifact_path(raw_report).read_text())
                duration = float((report.get("media") or {}).get("duration_s") or 1)
            except HTTPException:
                pass
        return _empty_series(name, duration)
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"{name} series is not ready")


@router.get("/{session_id}/timeline")
async def get_timeline(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """SPEC §8.4 lane payload written beside report artifacts (issue #47)."""
    session = _owned_session(session_id, current_user, db)
    _, outputs = _outputs_or_conflict(session, db)
    raw = outputs.get("timeline")
    if raw:
        return json.loads(_safe_artifact_path(raw).read_text())
    directory = _artifact_dir(outputs)
    if directory:
        candidate = (directory / "timeline.json").resolve()
        if candidate.is_file() and candidate.is_relative_to(MEDIA_ROOT):
            return json.loads(candidate.read_text())
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Timeline is not ready")


def _json_artifact(outputs: dict, key: str, filename: str) -> dict:
    raw = outputs.get(key)
    if raw:
        return json.loads(_safe_artifact_path(raw).read_text())
    directory = _artifact_dir(outputs)
    if directory:
        candidate = (directory / filename).resolve()
        if candidate.is_file() and candidate.is_relative_to(MEDIA_ROOT):
            return json.loads(candidate.read_text())
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"{key} is not ready")


@router.get("/{session_id}/body")
async def get_body(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """SPEC §8.7 Body-tab payload written beside report artifacts (issue #48)."""
    session = _owned_session(session_id, current_user, db)
    _, outputs = _outputs_or_conflict(session, db)
    return _json_artifact(outputs, "body", "body.json")


@router.get("/{session_id}/slides")
async def get_slides_tab(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """SPEC §8.7 Slides-tab filmstrip (issue #48)."""
    session = _owned_session(session_id, current_user, db)
    _, outputs = _outputs_or_conflict(session, db)
    return _json_artifact(outputs, "slides_tab", "slides_tab.json")


@router.get("/{session_id}/keyframe")
async def get_keyframe(
    session_id: str,
    i: int = Query(default=1, ge=1),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Slide keyframe JPEG for the Slides-tab filmstrip."""
    session = _owned_session(session_id, current_user, db)
    _, outputs = _outputs_or_conflict(session, db)
    directory = _artifact_dir(outputs)
    if not directory:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Keyframe is not ready")
    slides = _json_artifact(outputs, "slides", "slides.json")
    raw = None
    for slide in slides.get("slides") or []:
        if int(slide.get("index") or 0) == i:
            raw = slide.get("keyframe")
            break
    if not raw:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Keyframe is not ready")
    candidate = Path(raw).resolve()
    if not candidate.is_file() or not candidate.is_relative_to(MEDIA_ROOT):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Keyframe is not ready")
    return FileResponse(candidate, media_type="image/jpeg")


@router.post("/{session_id}/export/pdf", status_code=status.HTTP_202_ACCEPTED)
async def export_pdf(
    session_id: str,
    body: PdfExportRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Async Playwright PDF export (SPEC §7.5 / §8.9, issue #49)."""
    session = _owned_session(session_id, current_user, db)
    _, outputs = _outputs_or_conflict(session, db)
    directory = _artifact_dir(outputs)
    if not directory:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Report is not ready")
    include = bool(body.include_transcript) if body else False
    export_id = str(uuid.uuid4())
    dest = (MEDIA_ROOT / "exports" / export_id).resolve()
    if not dest.is_relative_to(MEDIA_ROOT):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid export path")
    dest.mkdir(parents=True, exist_ok=True, mode=0o700)
    meta = {
        "id": export_id,
        "session_id": str(session.id),
        "user_id": str(current_user.id),
        "status": "queued",
        "include_transcript": include,
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    (dest / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    celery = Celery("stagecoach-api", broker=REDIS_URL, backend=REDIS_URL)
    celery.send_task(
        "tasks.export_pdf",
        kwargs={
            "export_id": export_id,
            "session_id": str(session.id),
            "output_dir": str(directory),
            "dest_dir": str(dest),
            "include_transcript": include,
        },
    )
    return {"id": export_id, "status": "queued"}


@router.get("/{session_id}/sprite")
async def get_sprite(
    session_id: str,
    t: float = Query(default=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Sprite thumbnail every 5 s for timeline hover (SPEC §8.4)."""
    session = _owned_session(session_id, current_user, db)
    _, outputs = _outputs_or_conflict(session, db)
    directory = _artifact_dir(outputs)
    if not directory:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Sprite is not ready")
    idx = int(max(0.0, float(t)) // 5)
    candidate = (directory / "sprites" / f"sprite_{idx:04d}.jpg").resolve()
    if not candidate.is_file() or not candidate.is_relative_to(MEDIA_ROOT):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sprite is not ready")
    return FileResponse(candidate, media_type="image/jpeg")


@router.get("/{session_id}/media/playback")
async def get_playback_url(
    session_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Short-lived playback URL. TTL is at most 15 minutes (SPEC §7.5)."""
    session = _owned_session(session_id, current_user, db)
    _, outputs = _outputs_or_conflict(session, db)
    _artifact_from_outputs(outputs, "playback")
    expires_at = int(datetime.now(timezone.utc).timestamp()) + PLAYBACK_TTL_S
    signature = sign_playback(str(session.id), expires_at)
    base = str(request.base_url).rstrip("/")
    url = f"{base}/api/v1/sessions/{session.id}/media?exp={expires_at}&sig={signature}"
    return {
        "url": url,
        "expires_at": datetime.fromtimestamp(expires_at, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "expires_in_s": PLAYBACK_TTL_S,
    }


@router.get("/{session_id}/media")
async def get_playback_media(
    session_id: str,
    exp: Optional[int] = Query(default=None),
    sig: Optional[str] = Query(default=None),
    purpose: Optional[str] = Query(default=None),
    asset: Optional[str] = Query(default=None),
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    session = None
    if exp is not None and sig:
        now = int(datetime.now(timezone.utc).timestamp())
        export_link = purpose == "export"
        ttl = EXPORT_TTL_S if export_link else PLAYBACK_TTL_S
        if exp < now or exp - now > ttl:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Playback URL expired")
        valid = (
            verify_export_link(session_id, asset or "", exp, sig)
            if export_link
            else verify_playback(session_id, exp, sig)
        )
        if not valid:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid playback signature")
        session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    else:
        if current_user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
        session = _owned_session(session_id, current_user, db)
    _, outputs = _outputs_or_conflict(session, db)
    path = _artifact_from_outputs(outputs, "playback")
    return FileResponse(
        path,
        filename=f"{session.id}{path.suffix}",
        media_type=MEDIA_TYPES.get(path.suffix.casefold(), "application/octet-stream"),
    )


def _session_row_counts(db: Session, session: SessionModel) -> tuple[dict[str, int], list]:
    jobs = db.query(AnalysisJob).filter(AnalysisJob.session_id == session.id).all()
    job_ids = [job.id for job in jobs]
    counts = {
        "sessions": 1,
        "media_assets": db.query(MediaAsset).filter(MediaAsset.session_id == session.id).count(),
        "analysis_jobs": len(jobs),
        "job_steps": 0,
        "transcripts": 0,
        "metric_values": 0,
        "category_scores": 0,
        "overall_scores": 0,
        "evidence_items": 0,
        "insights": 0,
        "session_layouts": db.query(SessionLayout).filter(SessionLayout.session_id == session.id).count(),
    }
    if job_ids:
        counts["job_steps"] = db.query(JobStep).filter(JobStep.job_id.in_(job_ids)).count()
        counts["transcripts"] = db.query(Transcript).filter(Transcript.job_id.in_(job_ids)).count()
        counts["metric_values"] = db.query(MetricValue).filter(MetricValue.job_id.in_(job_ids)).count()
        counts["category_scores"] = db.query(CategoryScore).filter(CategoryScore.job_id.in_(job_ids)).count()
        counts["overall_scores"] = db.query(OverallScore).filter(OverallScore.job_id.in_(job_ids)).count()
        counts["evidence_items"] = db.query(EvidenceItem).filter(EvidenceItem.job_id.in_(job_ids)).count()
        counts["insights"] = db.query(Insight).filter(Insight.job_id.in_(job_ids)).count()
    return counts, job_ids


def _remaining_session_rows(db: Session, session_id, job_ids: list) -> dict[str, int]:
    remaining = {
        "sessions": db.query(SessionModel).filter(SessionModel.id == session_id).count(),
        "media_assets": db.query(MediaAsset).filter(MediaAsset.session_id == session_id).count(),
        "analysis_jobs": db.query(AnalysisJob).filter(AnalysisJob.session_id == session_id).count(),
        "job_steps": 0,
        "transcripts": 0,
        "metric_values": 0,
        "category_scores": 0,
        "overall_scores": 0,
        "evidence_items": 0,
        "insights": 0,
        "session_layouts": db.query(SessionLayout).filter(SessionLayout.session_id == session_id).count(),
    }
    if job_ids:
        remaining["job_steps"] = db.query(JobStep).filter(JobStep.job_id.in_(job_ids)).count()
        remaining["transcripts"] = db.query(Transcript).filter(Transcript.job_id.in_(job_ids)).count()
        remaining["metric_values"] = db.query(MetricValue).filter(MetricValue.job_id.in_(job_ids)).count()
        remaining["category_scores"] = db.query(CategoryScore).filter(CategoryScore.job_id.in_(job_ids)).count()
        remaining["overall_scores"] = db.query(OverallScore).filter(OverallScore.job_id.in_(job_ids)).count()
        remaining["evidence_items"] = db.query(EvidenceItem).filter(EvidenceItem.job_id.in_(job_ids)).count()
        remaining["insights"] = db.query(Insight).filter(Insight.job_id.in_(job_ids)).count()
    return remaining


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Hard-delete objects, derived artifacts, and DB rows; write a content-free audit."""
    session = _owned_session(session_id, current_user, db)
    session_uuid = session.id
    session_id_str = str(session_uuid)
    try:
        session_dir = local_session_dir(MEDIA_ROOT, session_uuid)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid session path") from exc

    prefix = session_object_prefix(current_user.id, session_uuid)
    store = build_object_store()
    db_rows, job_ids = _session_row_counts(db, session)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    request_row = DeletionRequest(
        user_id=current_user.id,
        scope="session",
        requested_at=now,
        verification={},
    )
    db.add(request_row)
    db.flush()

    local_deleted = delete_local_prefix(session_dir, MEDIA_ROOT)
    remote_deleted = store.delete_prefix(prefix)
    object_count = local_deleted + remote_deleted

    db.delete(session)
    db.flush()
    db.expire_all()

    remaining_local = count_files(session_dir)
    remaining_remote = store.remaining(prefix)
    db_left = _remaining_session_rows(db, session_uuid, job_ids)
    db_remaining = sum(db_left.values())
    verification = {
        "object_count": object_count,
        "local_remaining": remaining_local,
        "object_store_remaining": remaining_remote,
        "db_remaining": db_remaining,
        "db_rows": db_rows,
        "db_left": db_left,
        "search_index": "not_deployed",
    }
    assert_no_content(verification)
    request_row.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
    request_row.verification = verification
    details = audit_details(
        object_count=object_count,
        db_rows=db_rows,
        prefixes=["local", "object_store"],
    )
    db.add(
        AuditLog(
            actor_id=current_user.id,
            action="session.delete",
            target_type="session",
            target_id=session_id_str,
            at=datetime.now(timezone.utc).replace(tzinfo=None),
            ip_hash=ip_hash(request.client.host if request.client else None),
            details=details,
        )
    )
    db.commit()
    if remaining_local or remaining_remote or db_remaining:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Session delete left remaining artifacts",
        )
    return None
