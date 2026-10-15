"""Talk plan, goals, and objective scores (SPEC §7.3 / issue #55)."""

from datetime import datetime

from sqlalchemy import Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.models import Base
from app.models.user import uuid7


class TalkPlan(Base):
    __tablename__ = "talk_plans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title = Column(String(255), nullable=False)
    context_type = Column(String(50), nullable=False)
    description = Column(Text, nullable=True)
    audience = Column(JSONB, nullable=True)
    goal = Column(Text, nullable=True)
    slot_min = Column(Integer, nullable=True)
    qa_in_slot = Column(Boolean, nullable=False, default=False)
    qa_min = Column(Integer, nullable=True)
    language = Column(String(10), nullable=False, default="en")
    constraints = Column(JSONB, nullable=True)
    deck_asset_id = Column(UUID(as_uuid=True), nullable=True)
    script_text = Column(Text, nullable=True)
    outputs = Column(JSONB, nullable=True)
    version = Column(Integer, nullable=False, default=1)
    edit_history = Column(JSONB, nullable=False, default=list)
    status = Column(String(20), nullable=False, default="queued")
    talk_date = Column(Date, nullable=True)
    delivery_format = Column(String(20), nullable=True)
    known_habits = Column(JSONB, nullable=True)
    must_include = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class Goal(Base):
    __tablename__ = "goals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    metric_id = Column(String(80), nullable=True)
    category_id = Column(String(80), nullable=True)
    comparator = Column(String(16), nullable=False)
    target = Column(Float, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    achieved_at = Column(DateTime, nullable=True)


class ObjectiveScore(Base):
    __tablename__ = "objective_scores"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    job_id = Column(
        UUID(as_uuid=True),
        ForeignKey("analysis_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    talk_plan_id = Column(
        UUID(as_uuid=True),
        ForeignKey("talk_plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    objective_id = Column(String(80), nullable=False)
    status = Column(String(16), nullable=False)
    score = Column(Float, nullable=True)
    evidence_ids = Column(JSONB, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
