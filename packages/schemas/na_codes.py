"""Stable N/A reason codes for analysis categories (O1, ADR-070).

`na_code` is the enum the API, schema, and UI key off. `na_reason` stays the
human-readable fallback written next to it.
"""

from __future__ import annotations

from typing import Optional

NA_CODES = (
    "not_in_phase",
    "consent_video_off",
    "vision_unavailable",
    "camera_not_visible",
    "camera_too_small",
    "audio_only_chosen",
    "audio_only_media",
    "no_screen",
    "qa_not_detected",
    "qa_declared_none",
    "target_length_missing",
    "insufficient_speech",
    "hands_not_visible",
    "stage_mode",
    "no_slides",
    "model_unavailable",
    "camera_coverage_low",
    "not_applicable",
)

# Jonny Ive §S5 keys mapped onto the persisted enum (answer 8).
S5_TO_NA_CODE = {
    "not_in_phase": "not_in_phase",
    "consent_video_off": "consent_video_off",
    "vision_unavailable": "vision_unavailable",
    "camera_not_visible": "camera_not_visible",
    "camera_too_small": "camera_too_small",
    "audio_only_chosen": "audio_only_chosen",
    "no_screen": "no_screen",
    "qa_not_detected": "qa_not_detected",
    "qa_declared_none": "qa_declared_none",
    "target_length_missing": "target_length_missing",
    "insufficient_speech": "insufficient_speech",
    "hands_not_visible": "hands_not_visible",
}

_REASON_HINTS: tuple[tuple[str, str], ...] = (
    ("consent_denied", "consent_video_off"),
    ("consent is off", "consent_video_off"),
    ("video analysis is off", "consent_video_off"),
    ("video analysis consent", "consent_video_off"),
    ("video_analysis", "consent_video_off"),
    ("mediapipe", "vision_unavailable"),
    ("not installed", "vision_unavailable"),
    ("not available on this server", "vision_unavailable"),
    ("audio-only media", "audio_only_media"),
    ("audio only", "audio_only_chosen"),
    ("analyse audio only", "audio_only_chosen"),
    ("analyze audio only", "audio_only_chosen"),
    ("camera tile was too small", "camera_too_small"),
    ("median face height", "camera_too_small"),
    ("didn't find your camera", "camera_not_visible"),
    ("camera not visible", "camera_not_visible"),
    ("no shared screen", "no_screen"),
    ("visible screen", "no_screen"),
    ("screen segment", "no_screen"),
    ("coming soon", "not_in_phase"),
    ("not scored for on-stage", "stage_mode"),
    ("not scored for on stage", "stage_mode"),
    ("did not include a q&a", "qa_declared_none"),
    ("question/answer", "qa_not_detected"),
    ("q&a section", "qa_not_detected"),
    ("no q&a", "qa_declared_none"),
    ("said there was no q", "qa_declared_none"),
    ("target length", "target_length_missing"),
    ("two minutes of speech", "insufficient_speech"),
    ("s of speech", "insufficient_speech"),
    ("hands", "hands_not_visible"),
    ("no slides", "no_slides"),
    ("no deck", "no_slides"),
    ("language model", "model_unavailable"),
    ("didn't finish", "model_unavailable"),
    ("did not finish", "model_unavailable"),
    ("fills the frame", "camera_coverage_low"),
    ("camera coverage", "camera_coverage_low"),
)


def infer_na_code(reason: Optional[str], *, category_id: Optional[str] = None) -> Optional[str]:
    """Map a free-text `na_reason` (or an S5 key) onto the stable enum."""
    if not reason:
        return None
    key = reason.strip()
    if key in NA_CODES:
        return key
    mapped = S5_TO_NA_CODE.get(key)
    if mapped:
        return mapped
    lowered = key.lower()
    for needle, code in _REASON_HINTS:
        if needle in lowered:
            return code
    if category_id in {"screen_flow", "on_camera_presence", "online_engagement", "production_quality"}:
        if "on-stage" in lowered or "on stage" in lowered:
            return "stage_mode"
    return "not_applicable"
