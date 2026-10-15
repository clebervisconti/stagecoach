"""Stage Coach scoring engine.

Computes category and overall scores from metric values using
versioned configuration files.
"""

from .aggregation import aggregate_category, aggregate_overall
from .confidence import compute_category_confidence, compute_inclusion_factor
from .curves import interpolate_curve, validate_curve
from .engine import ScoringEngine
from .opportunities import rank_opportunities
from .time_budget import (
    build_cut_list,
    build_time_budget,
    rehearsal_plan,
)

__all__ = [
    "ScoringEngine",
    "interpolate_curve",
    "validate_curve",
    "compute_inclusion_factor",
    "compute_category_confidence",
    "aggregate_category",
    "aggregate_overall",
    "rank_opportunities",
    "build_time_budget",
    "build_cut_list",
    "rehearsal_plan",
]

__version__ = "0.1.0"
