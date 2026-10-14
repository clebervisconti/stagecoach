"""Generated strengths, weaknesses, and opportunities."""

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, UUID

from app.models import Base
from app.models.user import uuid7


class Insight(Base):
    __tablename__ = "insights"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    job_id = Column(UUID(as_uuid=True), ForeignKey("analysis_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    type = Column(String(20), nullable=False)
    rank = Column(Integer, nullable=False)
    category_id = Column(String(40), nullable=True)
    title = Column(String(120), nullable=False)
    body_md = Column(Text, nullable=True)
    fix_md = Column(Text, nullable=True)
    drill_ids = Column(ARRAY(Text), nullable=True)
    evidence_ids = Column(ARRAY(Text), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
