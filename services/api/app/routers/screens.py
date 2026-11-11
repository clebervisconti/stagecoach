"""Read the screen-flow view model. Measurement files stay the source of truth."""

from __future__ import annotations

import json
import time
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models.user import User
from app.routers import sessions as session_routes
from app.routers.sessions import _latest_job, _owned_session, sign_playback, verify_playback

router = APIRouter(prefix="/sessions", tags=["screens"])

PREVIEW_TTL_S = 15 * 60


def _job_dir(session_id: str, job_id: str) -> Path:
    root = session_routes.MEDIA_ROOT.resolve()
    directory = (session_routes.MEDIA_ROOT / session_id / job_id).resolve()
    if not directory.is_relative_to(root):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return directory


def _load_document(directory: Path) -> dict:
    path = directory / "screen_flow.json"
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _keyframe_url(session_id: str, index: int) -> str:
    expires = int(time.time()) + PREVIEW_TTL_S
    signature = sign_playback(f"{session_id}:screen:{index}", expires)
    return f"/api/v1/sessions/{session_id}/screens/keyframe/{index}?exp={expires}&sig={signature}"


def _contained_keyframe(directory: Path, raw: str) -> Path | None:
    if not raw or ".." in Path(raw).parts:
        return None
    candidate = Path(raw)
    resolved = candidate.resolve() if candidate.is_absolute() else (directory / candidate).resolve()
    root = session_routes.MEDIA_ROOT.resolve()
    job = directory.resolve()
    if not resolved.is_relative_to(job) or not resolved.is_relative_to(root):
        return None
    if not resolved.is_file():
        return None
    return resolved


@router.get("/{session_id}/screens")
async def get_screens(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Appendix B.2 view. 404 reason not_measured until the stage has written a file."""
    session = _owned_session(session_id, current_user, db)
    job = _latest_job(session, db)
    directory = _job_dir(str(session.id), str(job.id))
    document = _load_document(directory)
    if not document:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"reason": "not_measured"})
    segments = []
    for segment in document.get("segments") or []:
        view = dict(segment)
        index = int(view.get("index") or 0)
        if view.get("keyframe") and index >= 1:
            view["keyframe_url"] = _keyframe_url(str(session.id), index)
        segments.append(view)
    coaching = None
    flow_path = directory / "online_flow.json"
    if flow_path.is_file():
        try:
            loaded = json.loads(flow_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            loaded = None
        if isinstance(loaded, dict):
            coaching = {
                key: loaded.get(key)
                for key in (
                    "source",
                    "fallback",
                    "prompt_version",
                    "observations",
                    "drills",
                    "strengths",
                    "latency_s",
                    "provider",
                )
            }
    return {**document, "segments": segments, "coaching": coaching}


@router.get("/{session_id}/screens/keyframe/{index}")
async def get_screen_keyframe(
    session_id: str,
    index: int,
    exp: int = Query(...),
    sig: str = Query(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Signed keyframe. The path must stay inside the job directory."""
    session = _owned_session(session_id, current_user, db)
    if index < 1 or exp < int(time.time()) or not verify_playback(f"{session_id}:screen:{index}", exp, sig):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Preview link expired")
    job = _latest_job(session, db)
    directory = _job_dir(str(session.id), str(job.id))
    document = _load_document(directory)
    raw = None
    for segment in document.get("segments") or []:
        if int(segment.get("index") or 0) == index:
            raw = segment.get("keyframe")
            break
    if not raw:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Keyframe is not ready")
    path = _contained_keyframe(directory, str(raw))
    if path is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Keyframe is not ready")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "private, no-store"})
