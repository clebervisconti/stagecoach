"""Append-only audit log. Rows must not store session content (SPEC §7.3, §10.3)."""

from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.models import Base
from app.models.user import uuid7


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    actor_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action = Column(String(64), nullable=False)
    target_type = Column(String(64), nullable=False)
    target_id = Column(String(64), nullable=False, index=True)
    at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    ip_hash = Column(String(64), nullable=True)
    details = Column(JSONB, nullable=False, default=dict)
