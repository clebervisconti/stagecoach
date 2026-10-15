"""SQLAlchemy models for Stage Coach."""

from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

# Import all models so Alembic can discover them
from app.models.user import User  # noqa: F401, E402
from app.models.consent import Consent  # noqa: F401, E402
from app.models.session import Session  # noqa: F401, E402
from app.models.media_asset import MediaAsset  # noqa: F401, E402
from app.models.analysis_job import AnalysisJob  # noqa: F401, E402
from app.models.job_step import JobStep  # noqa: F401, E402
from app.models.scoring_config import ScoringConfig  # noqa: F401, E402
from app.models.transcript import Transcript  # noqa: F401, E402
from app.models.metric_value import MetricValue  # noqa: F401, E402
from app.models.category_score import CategoryScore  # noqa: F401, E402
from app.models.overall_score import OverallScore  # noqa: F401, E402
from app.models.evidence_item import EvidenceItem  # noqa: F401, E402
from app.models.insight import Insight  # noqa: F401, E402
from app.models.audit_log import AuditLog  # noqa: F401, E402
from app.models.deletion_request import DeletionRequest  # noqa: F401, E402
from app.models.talk_plan import Goal, ObjectiveScore, TalkPlan  # noqa: F401, E402

__all__ = [
    "Base",
    "User",
    "Consent",
    "Session",
    "MediaAsset",
    "AnalysisJob",
    "JobStep",
    "ScoringConfig",
    "Transcript",
    "MetricValue",
    "CategoryScore",
    "OverallScore",
    "EvidenceItem",
    "Insight",
    "AuditLog",
    "DeletionRequest",
    "TalkPlan",
    "Goal",
    "ObjectiveScore",
]
