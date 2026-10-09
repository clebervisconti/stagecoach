"""Session model."""

from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, Boolean, ForeignKey, Text, ARRAY
from sqlalchemy.dialects.postgresql import UUID

from app.models import Base
from app.models.user import uuid7


class Session(Base):
    """Recording sessions.
    
    One recording = one session.
    """
    __tablename__ = "sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    talk_plan_id = Column(UUID(as_uuid=True), nullable=True, comment="Link to talk plan (Phase 3)")
    title = Column(String(255), nullable=False)
    context_type = Column(
        String(50),
        nullable=False,
        comment="keynote, breakout, exec_briefing, sales_pitch, virtual_meeting, "
                "class_academic, other"
    )
    language = Column(String(10), nullable=False, comment="en, pt-BR, auto")
    slot_min = Column(Integer, nullable=True, comment="Target slot length in minutes")
    qa_in_slot = Column(Boolean, nullable=False, default=False)
    audience_desc = Column(Text, nullable=True)
    camera_setup = Column(
        String(50),
        nullable=False,
        comment="stage, to_camera, screen_recording, audio_only"
    )
    status = Column(
        String(20),
        nullable=False,
        default="created",
        comment="created, uploaded, processing, ready, partial, failed"
    )
    primary_speaker_label = Column(String(50), nullable=True, comment="For diarization")
    focus_areas = Column(ARRAY(String), nullable=True, comment="Up to 3 focus category IDs")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<Session(id={self.id}, title={self.title}, status={self.status})>"
