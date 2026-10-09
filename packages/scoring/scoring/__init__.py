"""Stage Coach scoring engine.

Computes category and overall scores from metric values using
versioned configuration files.
"""

from .engine import ScoringEngine
from .curves import interpolate_curve, validate_curve
from .confidence import compute_inclusion_factor, compute_category_confidence
from .aggregation import aggregate_category, aggregate_overall
from .opportunities import rank_opportunities

__all__ = [
    "ScoringEngine",
    "interpolate_curve",
    "validate_curve",
    "compute_inclusion_factor",
    "compute_category_confidence",
    "aggregate_category",
    "aggregate_overall",
    "rank_opportunities",
]

__version__ = "0.1.0"
