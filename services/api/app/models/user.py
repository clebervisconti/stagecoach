"""User model."""

from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text, Integer, ForeignKey
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
    retention_policy = Column(
        String(32),
        nullable=False,
        default="days_30",
        comment="after_analysis, days_30, until_delete",
    )
    llm_settings = Column(
        JSONB,
        comment="Chosen LLM provider, optional base_url and model. Never API keys.",
    )
    personal_baselines = Column(
        JSONB,
        nullable=True,
        comment="Per-language median/MAD after 3 sessions. Does not replace scores.",
    )
    layout_review_pref = Column(
        String(20),
        nullable=False,
        default="when_unsure",
        comment="always, when_unsure, never",
    )
    password_hash = Column(Text, nullable=True)
    email_verified_at = Column(DateTime, nullable=True)
    failed_logins = Column(Integer, nullable=False, default=0)
    locked_until = Column(DateTime, nullable=True)
    apple_sub = Column(String(255), nullable=True, unique=True, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True, index=True)

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email})>"


class AuthToken(Base):
    """One-time email-verification and password-reset tokens."""

    __tablename__ = "auth_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    purpose = Column(String(32), nullable=False)
    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
