"""Drill attempts and corrected transcripts."""

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.models import Base
from app.models.user import uuid7


class DrillAttempt(Base):
    __tablename__ = "drill_attempts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    drill_id = Column(String(80), nullable=False)
    source_session_id = Column(UUID(as_uuid=True), nullable=True)
    status = Column(String(20), nullable=False, default="ready")
    result = Column(JSONB, nullable=True)
    media_uri = Column(String(512), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class TranscriptRevision(Base):
    __tablename__ = "transcript_revisions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    session_id = Column(
        UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    body = Column(Text, nullable=False)
    signals = Column(JSONB, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
