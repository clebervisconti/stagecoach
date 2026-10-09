"""Opportunity ranking for improvement suggestions."""

from typing import Any


def rank_opportunities(
    categories: list[dict[str, Any]],
    context: str,
    config: dict[str, Any],
    focus_areas: list[str],
) -> list[dict[str, Any]]:
    """Rank improvement opportunities by impact.

    impact = W_c × (target_c − S_c) × C_c × tractability_c

    where:
    - W_c = category weight in this context
    - target_c = min(S_c + target_lift, 85)
    - S_c = current category score
    - C_c = category confidence
    - tractability_c = how quickly improvable (from config)

    Focus areas get a boost.

    Args:
        categories: List of category dicts
        context: Presentation context
        config: Full scoring config
        focus_areas: List of category IDs to boost

    Returns:
        List of opportunity dicts sorted by impact (highest first)
    """
    context_weights = config["weights"].get(context, {})
    opp_config = config.get("opportunities", {})
    target_lift = opp_config.get("target_lift", 25)
    tractability_boost = opp_config.get("tractability_boost", 1.25)
    min_impact = opp_config.get("min_impact_to_show", 5)

    opportunities = []

    for category in categories:
        cat_id = category["id"]
        score = category.get("score")
        confidence = category.get("confidence", 0.0)
        applicable = category.get("applicable", False)

        if not applicable or score is None or score >= 85:
            # Skip if N/A, no score, or already excellent
            continue

        weight = context_weights.get(cat_id, 0)
        if weight == 0:
            continue

        # Get tractability from category definition
        category_def = config["categories"].get(cat_id, {})
        tractability = category_def.get("tractability", 0.8)

        # Apply focus area boost
        if cat_id in focus_areas:
            tractability *= tractability_boost

        # Compute target and lift
        target = min(score + target_lift, 85)
        lift = target - score

        # Compute impact
        impact = weight * lift * confidence * tractability

        if impact >= min_impact:
            opportunities.append(
                {
                    "category_id": cat_id,
                    "current_score": score,
                    "target_score": target,
                    "lift": lift,
                    "impact": impact,
                    "weight": weight,
                    "confidence": confidence,
                    "tractability": tractability,
                    "is_focus_area": cat_id in focus_areas,
                }
            )

    # Sort by impact descending
    opportunities.sort(key=lambda x: x["impact"], reverse=True)

    # Return top opportunities (typically limited to 3 in the report)
    return opportunities
