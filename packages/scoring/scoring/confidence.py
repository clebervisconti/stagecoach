"""Confidence calculations and inclusion factors."""

from typing import Any


def compute_inclusion_factor(confidence: float, config: dict[str, Any]) -> float:
    """Compute the inclusion factor q from confidence c.

    Per §4.6.2 of SPEC:
    - q = 1 if c >= include_full (default 0.6)
    - q = (c - include_partial_from) / (include_full - include_partial_from)
      if include_partial_from <= c < include_full
    - q = 0 if c < include_partial_from (default 0.4)

    Args:
        confidence: Metric confidence in [0, 1]
        config: Confidence configuration dict

    Returns:
        Inclusion factor in [0, 1]
    """
    include_full = config.get("include_full", 0.6)
    include_partial_from = config.get("include_partial_from", 0.4)

    if confidence >= include_full:
        return 1.0
    elif confidence >= include_partial_from:
        # Linear ramp from 0 to 1
        result: float = (confidence - include_partial_from) / (include_full - include_partial_from)
        return result
    else:
        return 0.0


def compute_category_confidence(metrics: list[dict[str, Any]], config: dict[str, Any]) -> float:
    """Compute category-level confidence from sub-metrics.

    C_c = Σ w_k·c_k / Σ w_k over applicable sub-metrics

    Args:
        metrics: List of metric dicts with keys: weight, confidence, included
        config: Confidence configuration (not currently used)

    Returns:
        Category confidence in [0, 1]
    """
    total_weighted_confidence = 0.0
    total_weight = 0.0

    for metric in metrics:
        if not metric.get("included", False):
            continue

        weight = metric.get("weight", 0.0)
        confidence = metric.get("confidence", 0.0)

        total_weighted_confidence += weight * confidence
        total_weight += weight

    if total_weight == 0:
        return 0.0

    return total_weighted_confidence / total_weight


def get_confidence_label(confidence: float, config: dict[str, Any]) -> str:
    """Map confidence value to a label.

    Args:
        confidence: Confidence value in [0, 1]
        config: Confidence configuration with label thresholds

    Returns:
        "high", "medium", or "low"
    """
    labels = config.get("labels", {"high": 0.75, "medium": 0.5})

    if confidence >= labels["high"]:
        return "high"
    elif confidence >= labels["medium"]:
        return "medium"
    else:
        return "low"
