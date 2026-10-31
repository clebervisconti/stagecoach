"""Screen-flow measurement rows (online modes, E3-1–E3-4)."""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.models import Base
from app.models.user import uuid7


class ScreenFlow(Base):
    """One screen_flow.json document for a job. The file is the source of truth."""

    __tablename__ = "screen_flows"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    session_id = Column(
        UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_id = Column(
        UUID(as_uuid=True),
        ForeignKey("analysis_jobs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    version = Column(String(20), nullable=False)
    delivery_mode = Column(String(30), nullable=False)
    screen_visible_s = Column(Float, nullable=False, default=0)
    segment_count = Column(Integer, nullable=False, default=0)
    document = Column(JSONB, nullable=False)
    content_judgment = Column(Boolean, nullable=False, default=False)
    artifact_uri = Column(String(1024), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class ScreenSegment(Base):
    """One timed screen segment. Query copy of the document segments."""

    __tablename__ = "screen_segments"
    __table_args__ = (UniqueConstraint("job_id", "index", name="uq_screen_segments_job_index"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    job_id = Column(
        UUID(as_uuid=True),
        ForeignKey("analysis_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_id = Column(
        UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    index = Column(Integer, nullable=False)
    t_start = Column(Float, nullable=False)
    t_end = Column(Float, nullable=False)
    dwell_s = Column(Float, nullable=False)
    segment_type = Column(String(16), nullable=False)
    keyframe = Column(String(1024), nullable=True)
    ocr_word_count = Column(Integer, nullable=False, default=0)
    deck_page = Column(Integer, nullable=True)
    activity = Column(JSONB, nullable=False)
    transition_in = Column(JSONB, nullable=True)
    narration = Column(JSONB, nullable=False)
    flags = Column(JSONB, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
