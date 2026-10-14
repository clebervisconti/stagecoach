"""Pure metric functions for Phase 1 (SPEC §1.4, Appendix D, issue #25)."""

from .compute import compute_session_metrics, persist_session_metrics
from .confidence import asr_confidence, prosody_confidence
from .fluency import (
    FILLER_BENCHMARK_HARMFUL,
    FILLER_BENCHMARK_NO_PENALTY,
    combined_filler_rate,
    compute_fluency_metrics,
)
from .pace import compute_pace_metrics
from .prosody import compute_prosody_metrics
from .timing import compute_timing_metrics
from .types import MetricBundle, MetricResult, PauseEvent, ProsodyFrame, SectionPlan, Word

__all__ = [
    "FILLER_BENCHMARK_HARMFUL",
    "FILLER_BENCHMARK_NO_PENALTY",
    "MetricBundle",
    "MetricResult",
    "PauseEvent",
    "ProsodyFrame",
    "SectionPlan",
    "Word",
    "asr_confidence",
    "combined_filler_rate",
    "compute_fluency_metrics",
    "compute_pace_metrics",
    "compute_prosody_metrics",
    "compute_session_metrics",
    "compute_timing_metrics",
    "persist_session_metrics",
    "prosody_confidence",
]
