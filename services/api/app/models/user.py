"""User model."""

from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid

from app.models import Base


def uuid7() -> uuid.UUID:
    """Generate a UUID v7 (time-ordered).
    
    Note: Python's uuid module doesn't have v7 yet. This is a placeholder
    that uses v4 for now. In production, use a proper UUID v7 implementation.
    """
    return uuid.uuid4()


class User(Base):
    """User accounts.
    
    Hard delete on account deletion (after a grace period).
    """
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255))
    locale = Column(String(10), nullable=False, default="en")
    timezone = Column(String(50), default="UTC")
    accessibility_profile = Column(
        JSONB,
        comment="Disability/speech-difference preferences: seated, limited_mobility, "
                "one_handed, speech_difference, prefers_no_video_metrics"
    )
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True, index=True)

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email})>"
