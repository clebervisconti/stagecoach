"""Scoring config model."""

from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID

from app.models import Base
from app.models.user import uuid7


class ScoringConfig(Base):
    """Versioned scoring configurations.
    
    Immutable once used. Each analysis records which config version it used.
    """
    __tablename__ = "scoring_configs"

    version = Column(String(20), primary_key=True, comment="Semantic version (e.g., 1.0.0)")
    yaml = Column(Text, nullable=False, comment="Full YAML content")
    sha256 = Column(String(64), nullable=False, unique=True)
    notes = Column(Text, nullable=True, comment="Change notes for this version")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<ScoringConfig(version={self.version})>"
