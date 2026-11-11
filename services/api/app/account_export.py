"""Zip data export (SPEC §7.5 / §10.3). JSON plus 24 h signed media links."""

from __future__ import annotations

import hashlib
import hmac
import io
import json
import os
import zipfile
from pathlib import Path
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.auth import jwt as auth_jwt
from app.models.analysis_job import AnalysisJob
from app.models.category_score import CategoryScore
from app.models.consent import Consent
from app.models.evidence_item import EvidenceItem
from app.models.media_asset import MediaAsset
from app.models.overall_score import OverallScore
from app.models.session import Session as TalkSession
from app.models.screen_flow import ScreenFlow
from app.models.session_layout import SessionLayout
from app.models.talk_plan import Goal, TalkPlan
from app.models.transcript import Transcript
from app.models.user import User
from sqlalchemy.orm import Session

EXPORT_TTL_S = 24 * 60 * 60
ZIP_FILES = (
    "manifest.json",
    "user.json",
    "sessions.json",
    "scores.json",
    "evidence.json",
    "transcripts.json",
    "plans.json",
    "consents.json",
    "media_links.json",
    "layouts.json",
    "screen_flow.json",
    "online_flow.json",
)


def public_api_base(request_base: str | None = None) -> str:
    env = (os.getenv("STAGECOACH_PUBLIC_URL") or os.getenv("NEXTAUTH_URL") or "").rstrip("/")
    if env:
        return env
    return (request_base or "http://127.0.0.1:8000").rstrip("/")


def _secret() -> str:
    return auth_jwt.AUTH_SECRET


def sign_export_link(session_id: str, asset_id: str, expires_at: int) -> str:
    secret = _secret()
    if len(secret) < 32:
        raise RuntimeError("Export signing is not configured")
    payload = f"export:{session_id}:{asset_id}:{expires_at}".encode()
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


def verify_export_link(session_id: str, asset_id: str, expires_at: int, signature: str) -> bool:
    if len(_secret()) < 32:
        return False
    expected = sign_export_link(session_id, asset_id or "", expires_at)
    return hmac.compare_digest(expected, signature or "")


def _iso(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.strftime("%Y-%m-%dT%H:%M:%SZ")
        return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    if isinstance(value, UUID):
        return str(value)
    return value


def _row(mapping: dict[str, Any]) -> dict[str, Any]:
    return {key: _iso(value) for key, value in mapping.items()}


def media_link(
    *,
    session_id: str,
    asset_id: str,
    kind: str,
    storage_uri: str,
    expires_at: int,
    api_base: str,
) -> dict[str, Any]:
    signature = sign_export_link(session_id, asset_id, expires_at)
    url = (
        f"{api_base}/api/v1/sessions/{session_id}/media"
        f"?exp={expires_at}&sig={signature}&purpose=export&asset={asset_id}"
    )
    return {
        "session_id": session_id,
        "asset_id": asset_id,
        "kind": kind,
        "object_key": storage_uri,
        "url": url,
        "expires_at": datetime.fromtimestamp(expires_at, tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "expires_in_s": EXPORT_TTL_S,
    }


def pack_zip(files: dict[str, Any]) -> bytes:
    missing = [name for name in ZIP_FILES if name not in files]
    if missing:
        raise ValueError(f"export zip missing {missing}")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in ZIP_FILES:
            archive.writestr(
                name,
                json.dumps(files[name], indent=2, default=str),
                compress_type=zipfile.ZIP_DEFLATED,
            )
    return buffer.getvalue()


def export_filename(user_id: UUID | str) -> str:
    return f"stagecoach-export-{user_id}.zip"


def _online_flow_files(jobs: list) -> list[dict[str, Any]]:
    """Read coaching files from the job directory. Missing files stay an empty list."""
    root = Path(os.getenv("MEDIA_ROOT", "/data/stagecoach")).resolve()
    rows: list[dict[str, Any]] = []
    for job in jobs:
        path = (root / str(job.session_id) / str(job.id) / "online_flow.json").resolve()
        try:
            if not path.is_relative_to(root) or not path.is_file():
                continue
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(payload, dict):
            rows.append({"session_id": str(job.session_id), "job_id": str(job.id), "document": payload})
    return rows


def collect_export(
    db: Session,
    user: User,
    *,
    now: datetime | None = None,
    request_base: str | None = None,
) -> dict[str, Any]:
    """Build the zip payload from the caller's own rows. No live S3."""
    clock = now or datetime.utcnow()
    expires_at = int(clock.replace(tzinfo=UTC).timestamp()) + EXPORT_TTL_S
    api_base = public_api_base(request_base)

    sessions = (
        db.query(TalkSession)
        .filter(TalkSession.user_id == user.id)
        .order_by(TalkSession.created_at.asc())
        .all()
    )
    session_ids = [row.id for row in sessions]
    jobs = []
    if session_ids:
        jobs = db.query(AnalysisJob).filter(AnalysisJob.session_id.in_(session_ids)).all()
    job_ids = [row.id for row in jobs]
    job_session = {row.id: row.session_id for row in jobs}

    category_scores = []
    overall_scores = []
    evidence = []
    transcripts = []
    if job_ids:
        category_scores = db.query(CategoryScore).filter(CategoryScore.job_id.in_(job_ids)).all()
        overall_scores = db.query(OverallScore).filter(OverallScore.job_id.in_(job_ids)).all()
        evidence = db.query(EvidenceItem).filter(EvidenceItem.job_id.in_(job_ids)).all()
        transcripts = db.query(Transcript).filter(Transcript.job_id.in_(job_ids)).all()

    plans = db.query(TalkPlan).filter(TalkPlan.user_id == user.id).all()
    goals = db.query(Goal).filter(Goal.user_id == user.id).all()
    consents = (
        db.query(Consent)
        .filter(Consent.user_id == user.id)
        .order_by(Consent.granted_at.asc())
        .all()
    )
    assets = []
    layouts = []
    screen_flows = []
    if session_ids:
        assets = db.query(MediaAsset).filter(MediaAsset.session_id.in_(session_ids)).all()
        layouts = (
            db.query(SessionLayout)
            .filter(SessionLayout.session_id.in_(session_ids))
            .order_by(SessionLayout.created_at.asc())
            .all()
        )
        screen_flows = (
            db.query(ScreenFlow)
            .filter(ScreenFlow.session_id.in_(session_ids))
            .order_by(ScreenFlow.created_at.asc())
            .all()
        )

    scores = {
        "category_scores": [
            _row(
                {
                    "id": row.id,
                    "job_id": row.job_id,
                    "session_id": job_session.get(row.job_id),
                    "category_id": row.category_id,
                    "score": row.score,
                    "level": row.level,
                    "confidence": row.confidence,
                    "applicable": row.applicable,
                    "na_reason": row.na_reason,
                    "weight_used": row.weight_used,
                    "created_at": row.created_at,
                }
            )
            for row in category_scores
        ],
        "overall_scores": [
            _row(
                {
                    "job_id": row.job_id,
                    "session_id": job_session.get(row.job_id),
                    "overall": row.overall,
                    "coverage": row.coverage,
                    "overall_confidence": row.overall_confidence,
                    "display_band": row.display_band,
                    "context_type": row.context_type,
                    "config_version": row.config_version,
                    "created_at": row.created_at,
                }
            )
            for row in overall_scores
        ],
    }
    links = [
        media_link(
            session_id=str(row.session_id),
            asset_id=str(row.id),
            kind=row.kind,
            storage_uri=row.storage_uri,
            expires_at=expires_at,
            api_base=api_base,
        )
        for row in assets
    ]
    return {
        "manifest.json": {
            "schema": "stagecoach.export.v1",
            "exported_at": _iso(clock),
            "media_link_ttl_s": EXPORT_TTL_S,
            "files": list(ZIP_FILES),
        },
        "user.json": _row(
            {
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "locale": user.locale,
                "timezone": user.timezone,
                "accessibility_profile": user.accessibility_profile,
                "retention_policy": user.retention_policy,
                "llm_settings": user.llm_settings,
                "layout_review_pref": getattr(user, "layout_review_pref", "when_unsure"),
                "created_at": user.created_at,
            }
        ),
        "sessions.json": [
            _row(
                {
                    "id": row.id,
                    "title": row.title,
                    "context_type": row.context_type,
                    "language": row.language,
                    "slot_min": row.slot_min,
                    "qa_in_slot": row.qa_in_slot,
                    "audience_desc": row.audience_desc,
                    "camera_setup": row.camera_setup,
                    "delivery_mode": getattr(row, "delivery_mode", "stage"),
                    "source_kind": getattr(row, "source_kind", "upload"),
                    "status": row.status,
                    "talk_plan_id": row.talk_plan_id,
                    "created_at": row.created_at,
                }
            )
            for row in sessions
        ],
        "scores.json": scores,
        "evidence.json": [
            _row(
                {
                    "id": row.id,
                    "job_id": row.job_id,
                    "session_id": job_session.get(row.job_id),
                    "category_id": row.category_id,
                    "metric_id": row.metric_id,
                    "t_start": row.t_start,
                    "t_end": row.t_end,
                    "modality": row.modality,
                    "kind": row.kind,
                    "quote": row.quote,
                    "measurement": row.measurement,
                    "confidence": row.confidence,
                    "user_disputed": row.user_disputed,
                }
            )
            for row in evidence
        ],
        "transcripts.json": [
            _row(
                {
                    "id": row.id,
                    "job_id": row.job_id,
                    "session_id": job_session.get(row.job_id),
                    "language": row.language,
                    "language_prob": row.language_prob,
                    "asr_model": row.asr_model,
                    "words_uri": row.words_uri,
                    "mean_word_prob": row.mean_word_prob,
                    "created_at": row.created_at,
                }
            )
            for row in transcripts
        ],
        "plans.json": {
            "talk_plans": [
                _row(
                    {
                        "id": row.id,
                        "title": row.title,
                        "context_type": row.context_type,
                        "description": row.description,
                        "audience": row.audience,
                        "goal": row.goal,
                        "slot_min": row.slot_min,
                        "language": row.language,
                        "outputs": row.outputs,
                        "version": row.version,
                        "status": row.status,
                        "created_at": row.created_at,
                    }
                )
                for row in plans
            ],
            "goals": [
                _row(
                    {
                        "id": row.id,
                        "metric_id": row.metric_id,
                        "category_id": row.category_id,
                        "comparator": row.comparator,
                        "target": row.target,
                        "created_at": row.created_at,
                        "achieved_at": row.achieved_at,
                    }
                )
                for row in goals
            ],
        },
        "consents.json": [
            _row(
                {
                    "id": row.id,
                    "purpose": row.purpose,
                    "granted": row.granted,
                    "version": row.version,
                    "granted_at": row.granted_at,
                    "revoked_at": row.revoked_at,
                    "ip_country": row.ip_country,
                }
            )
            for row in consents
        ],
        "media_links.json": links,
        "layouts.json": [
            _row(
                {
                    "id": row.id,
                    "session_id": row.session_id,
                    "job_id": row.job_id,
                    "version": row.version,
                    "status": row.status,
                    "detector_version": row.detector_version,
                    "confidence": row.confidence,
                    "detected": row.detected,
                    "confirmed": row.confirmed,
                    "edit_count": row.edit_count,
                    "created_at": row.created_at,
                    "confirmed_at": row.confirmed_at,
                }
            )
            for row in layouts
        ],
        "screen_flow.json": [
            _row(
                {
                    "id": row.id,
                    "session_id": row.session_id,
                    "job_id": row.job_id,
                    "version": row.version,
                    "delivery_mode": row.delivery_mode,
                    "screen_visible_s": row.screen_visible_s,
                    "segment_count": row.segment_count,
                    "content_judgment": row.content_judgment,
                    "document": row.document,
                    "created_at": row.created_at,
                }
            )
            for row in screen_flows
        ],
        "online_flow.json": _online_flow_files(jobs),
    }
