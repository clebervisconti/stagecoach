"""Per-job category scores."""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.models import Base
from app.models.user import uuid7


class CategoryScore(Base):
    __tablename__ = "category_scores"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    job_id = Column(UUID(as_uuid=True), ForeignKey("analysis_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    category_id = Column(String(40), nullable=False)
    score = Column(Integer, nullable=True)
    level = Column(Integer, nullable=True)
    confidence = Column(Float, nullable=True)
    applicable = Column(Boolean, nullable=False, default=True)
    na_reason = Column(Text, nullable=True)
    weight_used = Column(Float, nullable=True)
    explanation = Column(JSONB, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
