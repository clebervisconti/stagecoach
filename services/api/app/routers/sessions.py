"""Session endpoints - Phase 0 implementation."""

import hashlib
import os
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models.user import User
from app.models.session import Session as SessionModel
from app.models.media_asset import MediaAsset

router = APIRouter(prefix="/sessions", tags=["sessions"])

# Configuration
TUS_ENDPOINT = os.getenv("TUS_ENDPOINT", "http://localhost:1080/files/")
MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024  # 2 GB
DEFAULT_RETENTION_DAYS = 90


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
    camera_setup: str = Field(
        ...,
        pattern="^(stage|to_camera|screen_recording|audio_only)$"
    )


class SessionResponse(BaseModel):
    """Session response."""
    id: str
    title: str
    status: str
    upload: dict


@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    session_data: SessionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create session and return tus upload URL (Phase 0)."""
    session = SessionModel(
        user_id=current_user.id,
        title=session_data.title,
        context_type=session_data.context_type,
        language=session_data.language,
        slot_min=session_data.slot_min,
        qa_in_slot=session_data.qa_in_slot,
        audience_desc=session_data.audience_desc,
        camera_setup=session_data.camera_setup,
        status="created",
    )
    
    db.add(session)
    db.commit()
    db.refresh(session)
    
    tus_url = f"{TUS_ENDPOINT}{session.id}"
    
    return SessionResponse(
        id=str(session.id),
        title=session.title,
        status=session.status,
        upload={
            "tus_url": tus_url,
            "max_size_bytes": MAX_FILE_SIZE,
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
    
    return {"sessions": [
        {
            "id": str(s.id),
            "title": s.title,
            "status": s.status,
            "created_at": s.created_at.isoformat(),
        }
        for s in sessions
    ]}
