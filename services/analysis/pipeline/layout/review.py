"""Layout-review decision (spec §9.2.6, OD-3)."""

from __future__ import annotations

from typing import Optional

REVIEW_REASONS = {
    "camera_tile_low_confidence",
    "screen_region_unclear",
    "primary_speaker_unclear",
    "many_layout_changes",
    "no_regions_found",
}

CONFIDENCE_REVIEW = 0.80
SEGMENT_REVIEW = 0.60
ALWAYS_REVIEW = 0.50
FIRST_ONLINE_REVIEWS = 3


def needs_layout_review(
    *,
    pref: str = "when_unsure",
    confirmed_count: int = 0,
    confidence: float = 1.0,
    segment_confidences: Optional[list[float]] = None,
    review_reason: Optional[str] = None,
    n_segments: int = 1,
) -> bool:
    segs = segment_confidences or []
    if confidence < ALWAYS_REVIEW:
        return True
    if pref == "never":
        return False
    if pref == "always":
        return True
    if confirmed_count < FIRST_ONLINE_REVIEWS:
        return True
    if confidence < CONFIDENCE_REVIEW:
        return True
    if any(value < SEGMENT_REVIEW for value in segs):
        return True
    if n_segments > 6:
        return True
    if review_reason:
        return True
    return False
