"""Shared dataclasses for Phase 1 metric functions (SPEC §1.4)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional


@dataclass(frozen=True)
class Word:
    """One token with timestamps from ASR or a synthetic fixture."""

    text: str
    start: float
    end: float
    probability: float = 1.0


@dataclass(frozen=True)
class PauseEvent:
    """A detected pause.

    `position` is `boundary`, `mid_sentence`, or `unknown` (SPEC §4.4.9).
    """

    start: float
    end: float
    position: str = "unknown"

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


@dataclass(frozen=True)
class ProsodyFrame:
    """One 10 ms prosody sample (SPEC §6.4)."""

    time_s: float
    f0_hz: Optional[float]
    f0_st: Optional[float]
    voiced: bool
    intensity_db: Optional[float]


@dataclass(frozen=True)
class SectionPlan:
    """Planned vs actual section duration for time management."""

    name: str
    planned_s: float
    actual_s: float


@dataclass(frozen=True)
class MetricResult:
    """One scored sub-metric. `id` and `unit` match scoring.yaml exactly."""

    id: str
    value: Optional[float]
    unit: str
    basis: str
    source: str
    confidence: float
    applicable: bool = True
    failure_mode: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MetricBundle:
    """All Phase 1 voice/time metrics plus confidence diagnostics."""

    metrics: dict[str, MetricResult] = field(default_factory=dict)
    asr_confidence: float = 0.0
    prosody_confidence: float = 0.0
    combined_filler_rate_per_min: Optional[float] = None
    filler_benchmark: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "metrics": {k: v.to_dict() for k, v in self.metrics.items()},
            "asr_confidence": self.asr_confidence,
            "prosody_confidence": self.prosody_confidence,
            "combined_filler_rate_per_min": self.combined_filler_rate_per_min,
            "filler_benchmark": self.filler_benchmark,
        }
