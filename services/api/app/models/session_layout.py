"""Detected and confirmed session layouts (online modes)."""

from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.models import Base
from app.models.user import uuid7


class SessionLayout(Base):
    """One detected (and optional confirmed) layout version for a job."""

    __tablename__ = "session_layouts"
    __table_args__ = (UniqueConstraint("job_id", "version", name="uq_session_layouts_job_version"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    session_id = Column(
        UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_id = Column(
        UUID(as_uuid=True),
        ForeignKey("analysis_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version = Column(Integer, nullable=False, default=1)
    status = Column(
        String(20),
        nullable=False,
        comment="detected, auto_confirmed, confirmed, corrected",
    )
    detector_version = Column(String(20), nullable=False)
    confidence = Column(Float, nullable=False)
    detected = Column(JSONB, nullable=False)
    confirmed = Column(JSONB, nullable=True)
    edit_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    confirmed_at = Column(DateTime, nullable=True)
