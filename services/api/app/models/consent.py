"""Consent model."""

from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from app.models import Base
from app.models.user import uuid7


class Consent(Base):
    """User consents for data processing.
    
    Append-only table. Current state = latest per purpose.
    """
    __tablename__ = "consents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    purpose = Column(
        String(50),
        nullable=False,
        comment="Purpose: video_analysis, expression_analysis, keep_detailed_tracking, "
                "research_use, benchmarks"
    )
    granted = Column(Boolean, nullable=False)
    version = Column(String(64), nullable=False, comment="Policy text hash")
    granted_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    revoked_at = Column(DateTime, nullable=True)
    ip_country = Column(String(2), nullable=True, comment="ISO 3166-1 alpha-2")

    def __repr__(self) -> str:
        return f"<Consent(user_id={self.user_id}, purpose={self.purpose}, granted={self.granted})>"
