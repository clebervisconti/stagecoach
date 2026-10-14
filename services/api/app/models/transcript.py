"""Transcript artifact pointer (word-level JSON lives in object storage)."""

from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID

from app.models import Base
from app.models.user import uuid7


class Transcript(Base):
    __tablename__ = "transcripts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    job_id = Column(UUID(as_uuid=True), ForeignKey("analysis_jobs.id", ondelete="CASCADE"), nullable=False, unique=True)
    language = Column(String(10), nullable=False)
    language_prob = Column(Float, nullable=True)
    asr_model = Column(String(128), nullable=True)
    words_uri = Column(String(512), nullable=True)
    mean_word_prob = Column(Float, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
