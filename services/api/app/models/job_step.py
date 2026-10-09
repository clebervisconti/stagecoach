"""Job step model."""

from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.models import Base
from app.models.user import uuid7


class JobStep(Base):
    """Pipeline stage execution records.
    
    Enables re-running individual stages and debugging pipeline failures.
    """
    __tablename__ = "job_steps"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    job_id = Column(UUID(as_uuid=True), ForeignKey("analysis_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    stage = Column(
        String(50),
        nullable=False,
        comment="ingest, asr, audio_features, vision, slides, content_llm, "
                "fusion_scoring, report"
    )
    stage_version = Column(String(20), nullable=False)
    status = Column(
        String(20),
        nullable=False,
        default="pending",
        comment="pending, running, completed, partial, failed"
    )
    attempt = Column(Integer, nullable=False, default=1)
    input_hash = Column(String(64), nullable=True, comment="Hash of inputs for idempotency")
    output_uris = Column(JSONB, nullable=True, comment="Storage URIs of outputs")
    metrics = Column(
        JSONB,
        nullable=True,
        comment="duration_s, frames_processed, tokens_used, etc."
    )
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    error = Column(JSONB, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<JobStep(id={self.id}, stage={self.stage}, status={self.status})>"
