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

__all__ = [
    "Base",
    "User",
    "Consent",
    "Session",
    "MediaAsset",
    "AnalysisJob",
    "JobStep",
    "ScoringConfig",
]
