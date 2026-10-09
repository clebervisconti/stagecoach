"""Category and overall score aggregation."""

from typing import Any

from .confidence import compute_category_confidence, get_confidence_label


def aggregate_category(
    category_id: str,
    category_def: dict[str, Any],
    metrics: list[dict[str, Any]],
    context: str,
    config: dict[str, Any],
) -> dict[str, Any]:
    """Aggregate sub-metric scores into a category score.

    S_c = Σ_k (w_k · q_k · s_k) / Σ_k (w_k · q_k)

    Args:
        category_id: Category identifier
        category_def: Category definition from config
        metrics: List of metric dicts with:
                 id, score, confidence, inclusion_factor, weight
        context: Presentation context
        config: Full scoring config

    Returns:
        Dict with: score, level, confidence, applicable, na_reason
    """
    metric_defs = category_def.get("metrics", {})

    # Check if category is applicable
    # In a real implementation, check min_evidence against actual data
    # For now, assume applicable if we have metrics
    # min_evidence = category_def.get("min_evidence", {})
    applicable = len(metrics) > 0
    na_reason = None if applicable else "No metrics provided"

    if not applicable:
        return {
            "score": None,
            "level": None,
            "confidence": 0.0,
            "confidence_label": "low",
            "applicable": False,
            "na_reason": na_reason,
        }

    # Aggregate scores using weighted inclusion factors
    total_weighted_score = 0.0
    total_weight = 0.0

    enriched_metrics = []
    for metric in metrics:
        metric_id = metric["id"]
        metric_def = metric_defs.get(metric_id, {})

        # Get metric weight (may be context-dependent)
        weight = metric_def.get("weight", 0.0)

        # Check for context-dependent weights
        context_weights = category_def.get("context_dependent_weights", {})
        if metric_id in context_weights:
            context_weight = context_weights[metric_id].get(context)
            if context_weight is not None:
                weight = context_weight

        metric["weight"] = weight
        metric["included"] = metric.get("inclusion_factor", 0) > 0

        if metric["included"] and metric.get("score") is not None:
            inclusion_factor = metric["inclusion_factor"]
            score = metric["score"]

            total_weighted_score += weight * inclusion_factor * score
            total_weight += weight * inclusion_factor

        enriched_metrics.append(metric)

    # Compute category score
    if total_weight == 0:
        category_score = None
        level = None
    else:
        category_score = total_weighted_score / total_weight
        # Clamp to [0, 100]
        category_score = max(0, min(100, category_score))
        # Compute level: ceil(score / 20), clamped to [1, 5]
        level = max(1, min(5, int((category_score - 0.01) // 20) + 1))

    # Compute category confidence
    confidence = compute_category_confidence(enriched_metrics, config["confidence"])
    confidence_label = get_confidence_label(confidence, config["confidence"])

    return {
        "score": category_score,
        "level": level,
        "confidence": confidence,
        "confidence_label": confidence_label,
        "applicable": True,
        "na_reason": None,
        "metrics": enriched_metrics,
    }


def aggregate_overall(
    categories: list[dict[str, Any]],
    context: str,
    config: dict[str, Any],
) -> dict[str, Any]:
    """Aggregate category scores into an overall score.

    Overall = Σ_{c ∈ applicable} W_c · S_c  /  Σ_{c ∈ applicable} W_c
    Coverage = Σ_{c ∈ applicable} W_c / 100

    Args:
        categories: List of category dicts with:
                   id, score, confidence, applicable
        context: Presentation context
        config: Full scoring config

    Returns:
        Dict with: score, level, coverage, confidence, display_band, partial
    """
    context_weights = config["weights"].get(context, {})
    confidence_config = config["confidence"]
    category_min = confidence_config.get("category_min_for_overall", 0.5)

    total_weighted_score = 0.0
    total_weight = 0.0
    total_possible_weight = 0.0
    total_weighted_confidence = 0.0

    for category in categories:
        cat_id = category["id"]
        weight = context_weights.get(cat_id, 0)
        total_possible_weight += weight

        # Include only if applicable and confidence >= threshold
        applicable = category.get("applicable", False)
        confidence = category.get("confidence", 0.0)
        score = category.get("score")

        if applicable and confidence >= category_min and score is not None:
            total_weighted_score += weight * score
            total_weighted_confidence += weight * confidence
            total_weight += weight

    # Compute overall score
    if total_weight == 0:
        overall_score = None
        level = None
        coverage = 0.0
        overall_confidence = 0.0
    else:
        overall_score = total_weighted_score / total_weight
        overall_score = max(0, min(100, overall_score))
        level = max(1, min(5, int((overall_score - 0.01) // 20) + 1))
        coverage = total_weight / 100.0  # Assumes total_possible_weight = 100
        overall_confidence = total_weighted_confidence / total_weight

    # Display band: ± round((1 - confidence) * factor)
    display_band_factor = config["overall"].get("display_band_factor", 10)
    if overall_confidence > 0:
        display_band = int(round((1 - overall_confidence) * display_band_factor))
    else:
        display_band = display_band_factor

    # Partial if coverage is too low
    partial_threshold = config["overall"].get("partial_if_coverage_below", 0.6)
    partial = coverage < partial_threshold if coverage > 0 else True

    return {
        "score": overall_score,
        "level": level,
        "coverage": coverage,
        "confidence": overall_confidence,
        "confidence_label": get_confidence_label(overall_confidence, confidence_config),
        "display_band": display_band,
        "partial": partial,
    }
