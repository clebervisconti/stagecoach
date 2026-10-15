"""Personal-baseline median / MAD and vs-your-baseline z (SPEC §4.7.3 / issue #66)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from statistics import median
from typing import Any

MIN_SESSIONS = 3
MAD_SCALE = 1.4826


@dataclass(frozen=True)
class MetricBaseline:
    metric_id: str
    language: str
    n: int
    median: float
    mad: float


@dataclass(frozen=True)
class BaselineSnapshot:
    """Serializable store for per-metric baselines (JSONB later; no Alembic here)."""

    language: str
    n_sessions: int
    metrics: dict[str, MetricBaseline]


def _median(values: Sequence[float]) -> float:
    return float(median(values))


def mean_absolute_deviation(values: Sequence[float]) -> float:
    if not values:
        raise ValueError("MAD needs at least one value")
    mid = _median(values)
    return _median([abs(value - mid) for value in values])


def baseline_for_metric(
    metric_id: str,
    values: Sequence[float],
    language: str,
) -> MetricBaseline | None:
    """Return median/MAD after ≥ 3 same-language sessions; otherwise None."""
    if len(values) < MIN_SESSIONS:
        return None
    return MetricBaseline(
        metric_id=metric_id,
        language=language,
        n=len(values),
        median=_median(values),
        mad=mean_absolute_deviation(values),
    )


def build_snapshot(
    per_metric: Mapping[str, Sequence[float]],
    language: str,
    n_sessions: int,
) -> BaselineSnapshot | None:
    if n_sessions < MIN_SESSIONS:
        return None
    metrics: dict[str, MetricBaseline] = {}
    for metric_id, values in per_metric.items():
        row = baseline_for_metric(metric_id, values, language)
        if row is not None:
            metrics[metric_id] = row
    if not metrics:
        return None
    return BaselineSnapshot(language=language, n_sessions=n_sessions, metrics=metrics)


def z_badge(raw_value: float, baseline: MetricBaseline) -> float | None:
    """z = (x − median) / (1.4826 · MAD). None when MAD is 0."""
    if baseline.mad == 0:
        return None
    return (raw_value - baseline.median) / (MAD_SCALE * baseline.mad)


def snapshot_to_dict(snapshot: BaselineSnapshot) -> dict[str, Any]:
    return {
        "language": snapshot.language,
        "n_sessions": snapshot.n_sessions,
        "metrics": {key: asdict(value) for key, value in snapshot.metrics.items()},
    }


def keep_population_score(population_score: float, _z: float | None) -> float:
    """Scores stay on population curves; the badge does not replace them."""
    return population_score
