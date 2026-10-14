"""Accessibility profile for metric applicability (SPEC §10.6, §10.7, issue #40).

Stored as user preference data, never inferred. Keys match the users table
comment in SPEC §7.3. Wheelchair is treated as seated for locomotion/sway.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

PROFILE_KEYS = (
    "seated",
    "wheelchair",
    "limited_mobility",
    "one_handed",
    "speech_difference",
    "prefers_no_video_metrics",
    "low_vision",
)

# Category 12: which gb_* ids the profile turns off (not a penalty).
SEATED_DISABLE = ("gb_sway_index", "gb_purposeful_movement")
LIMITED_MOBILITY_DISABLE = (
    "gb_sway_index",
    "gb_purposeful_movement",
    "gb_gesture_activity_ratio",
    "gb_gesture_space_ratio",
    "gb_gesture_speech_sync",
)


def normalize_profile(raw: Optional[dict[str, Any]]) -> dict[str, bool]:
    """Keep only known boolean flags. Wheelchair implies seated."""
    src = raw or {}
    out = {key: bool(src.get(key)) for key in PROFILE_KEYS}
    if out["wheelchair"]:
        out["seated"] = True
    return out


def persist_accessibility(output_dir: Path, profile: Optional[dict[str, Any]]) -> dict[str, bool]:
    snapshot = normalize_profile(profile)
    path = Path(output_dir) / "accessibility.json"
    path.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
    return snapshot


def load_accessibility(output_dir: Path) -> dict[str, bool]:
    path = Path(output_dir) / "accessibility.json"
    if not path.exists():
        return normalize_profile(None)
    try:
        return normalize_profile(json.loads(path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, TypeError):
        return normalize_profile(None)


def disabled_gesture_metrics(profile: Optional[dict[str, Any]]) -> set[str]:
    """gb_* ids that must be N/A for this profile. Empty if video metrics are allowed."""
    flags = normalize_profile(profile)
    disabled: set[str] = set()
    if flags["seated"] or flags["wheelchair"]:
        disabled.update(SEATED_DISABLE)
    if flags["limited_mobility"]:
        disabled.update(LIMITED_MOBILITY_DISABLE)
    return disabled


def video_metrics_opted_out(profile: Optional[dict[str, Any]]) -> bool:
    return normalize_profile(profile)["prefers_no_video_metrics"]


def gesture_na_reason(profile: Optional[dict[str, Any]]) -> Optional[str]:
    flags = normalize_profile(profile)
    if flags["prefers_no_video_metrics"]:
        return "Video body metrics are off in the accessibility profile."
    return None
