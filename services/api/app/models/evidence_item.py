"""Clickable evidence items, including user disputes."""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID

from app.models import Base
from app.models.user import uuid7


class EvidenceItem(Base):
    __tablename__ = "evidence_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    job_id = Column(UUID(as_uuid=True), ForeignKey("analysis_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    category_id = Column(String(40), nullable=False)
    metric_id = Column(String(80), nullable=True)
    t_start = Column(Float, nullable=False)
    t_end = Column(Float, nullable=False)
    modality = Column(String(20), nullable=False)
    kind = Column(String(20), nullable=False)
    quote = Column(Text, nullable=True)
    measurement = Column(JSONB, nullable=True)
    seg_ids = Column(ARRAY(Text), nullable=True)
    confidence = Column(Float, nullable=True)
    user_disputed = Column(Boolean, nullable=False, default=False)
    dispute_note = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
