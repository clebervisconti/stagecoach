"""Per-job sub-metric values."""

from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.models import Base
from app.models.user import uuid7


class MetricValue(Base):
    __tablename__ = "metric_values"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    job_id = Column(UUID(as_uuid=True), ForeignKey("analysis_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    metric_id = Column(String(80), nullable=False)
    raw_value = Column(Float, nullable=True)
    unit = Column(String(64), nullable=True)
    score = Column(Float, nullable=True)
    confidence = Column(Float, nullable=True)
    source_key = Column(String(32), nullable=True)
    details = Column(JSONB, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
