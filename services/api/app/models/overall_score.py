"""Per-job overall score."""

from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID

from app.models import Base


class OverallScore(Base):
    __tablename__ = "overall_scores"

    job_id = Column(UUID(as_uuid=True), ForeignKey("analysis_jobs.id", ondelete="CASCADE"), primary_key=True)
    overall = Column(Integer, nullable=True)
    coverage = Column(Float, nullable=True)
    overall_confidence = Column(Float, nullable=True)
    display_band = Column(Integer, nullable=True)
    context_type = Column(String(50), nullable=True)
    config_version = Column(String(20), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
