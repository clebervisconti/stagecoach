"""Analysis job model."""

from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.models import Base
from app.models.user import uuid7


class AnalysisJob(Base):
    """Analysis pipeline jobs.
    
    A session can have several jobs (re-analysis with different configs).
    """
    __tablename__ = "analysis_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    scoring_config_version = Column(String(20), nullable=False)
    pipeline_version = Column(String(20), nullable=False)
    status = Column(
        String(20),
        nullable=False,
        default="pending",
        comment="pending, running, completed, failed"
    )
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    error = Column(JSONB, nullable=True, comment="Error details if failed")
    cost = Column(JSONB, nullable=True, comment="Tokens, GPU seconds, etc.")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    def __repr__(self) -> str:
        return f"<AnalysisJob(id={self.id}, session_id={self.session_id}, status={self.status})>"
