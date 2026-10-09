"""Media asset model."""

from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, Float, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.models import Base
from app.models.user import uuid7


class MediaAsset(Base):
    """Media files and artifacts.
    
    Lifecycle rules delete objects from storage when retention_until passes.
    """
    __tablename__ = "media_assets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    kind = Column(
        String(50),
        nullable=False,
        comment="original, analysis_proxy, playback, audio16k, deck, keyframe, sprite"
    )
    storage_uri = Column(String(512), nullable=False, comment="S3/MinIO URI")
    bytes = Column(Integer, nullable=False)
    duration_s = Column(Float, nullable=True, comment="For video/audio")
    codec_info = Column(JSONB, nullable=True)
    sha256 = Column(String(64), nullable=False)
    retention_until = Column(DateTime, nullable=False, comment="When to delete from storage")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<MediaAsset(id={self.id}, kind={self.kind}, session_id={self.session_id})>"
