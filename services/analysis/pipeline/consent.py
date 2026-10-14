"""Vision consent gates (issue #37, SPEC §5.4, §6.5).

Video analysis runs only when video_analysis is granted.
Facial expression metrics additionally require expression_analysis.
Raw landmarks are kept only when keep_detailed_tracking is granted.
Frames are never stored as vision features.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Optional

CONSENT_PURPOSES = (
    "video_analysis",
    "expression_analysis",
    "keep_detailed_tracking",
    "research_use",
    "benchmarks",
)

VISION_CATEGORIES = ("gestures_body", "eye_contact", "facial_affect")


@dataclass(frozen=True)
class VisionDecision:
    run_pose: bool
    run_hands: bool
    run_face_landmarks: bool
    run_expression_metrics: bool
    keep_raw_landmarks: bool
    skip_reason: Optional[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _granted(snapshot: Optional[dict[str, Any]], purpose: str) -> bool:
    if not snapshot:
        return False
    purposes = snapshot.get("purposes") or {}
    row = purposes.get(purpose) or {}
    return bool(row.get("granted"))


def normalize_snapshot(consents: Optional[dict[str, Any]]) -> dict[str, Any]:
    purposes = {}
    incoming = (consents or {}).get("purposes") or {}
    for purpose in CONSENT_PURPOSES:
        row = incoming.get(purpose) or {}
        purposes[purpose] = {
            "granted": bool(row.get("granted")),
            "granted_at": row.get("granted_at"),
            "revoked_at": row.get("revoked_at"),
            "version": row.get("version"),
        }
    return {
        "policy_id": (consents or {}).get("policy_id") or "1.0.0",
        "policy_version": (consents or {}).get("policy_version"),
        "purposes": purposes,
    }


def decide_vision(consents: Optional[dict[str, Any]]) -> VisionDecision:
    snapshot = normalize_snapshot(consents)
    video = _granted(snapshot, "video_analysis")
    expression = video and _granted(snapshot, "expression_analysis")
    keep = video and _granted(snapshot, "keep_detailed_tracking")
    if not video:
        return VisionDecision(
            run_pose=False,
            run_hands=False,
            run_face_landmarks=False,
            run_expression_metrics=False,
            keep_raw_landmarks=False,
            skip_reason="consent_denied:video_analysis",
        )
    return VisionDecision(
        run_pose=True,
        run_hands=True,
        run_face_landmarks=True,
        run_expression_metrics=expression,
        keep_raw_landmarks=keep,
        skip_reason=None,
    )


def persist_consent_snapshot(output_dir: Path, consents: Optional[dict[str, Any]]) -> dict[str, Any]:
    snapshot = normalize_snapshot(consents)
    snapshot["decision"] = decide_vision(snapshot).to_dict()
    path = Path(output_dir) / "consents.json"
    path.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
    return snapshot


def run_vision_if_allowed(
    consents: Optional[dict[str, Any]],
    runner: Optional[Callable[[VisionDecision], Any]] = None,
) -> dict[str, Any]:
    """Never call runner unless video_analysis is granted."""
    decision = decide_vision(consents)
    if not decision.run_pose:
        return {
            "status": "skipped",
            "reason": decision.skip_reason,
            "called": False,
            "decision": decision.to_dict(),
        }
    if runner is None:
        return {
            "status": "allowed",
            "reason": None,
            "called": False,
            "decision": decision.to_dict(),
        }
    result = runner(decision)
    return {
        "status": "ran",
        "reason": None,
        "called": True,
        "decision": decision.to_dict(),
        "result": result,
    }


def video_category_na_reason(category_id: str, consents: Optional[dict[str, Any]]) -> str:
    decision = decide_vision(consents)
    if category_id == "facial_affect":
        if not decision.run_expression_metrics:
            return "Expression analysis is off; facial movement signals were not processed."
        return "Vision stage was not run; expression signals need a visible face."
    if category_id in {"gestures_body", "eye_contact"}:
        if not decision.run_pose:
            return "Video analysis consent is off; pose and face landmarks were not processed."
        if category_id == "gestures_body":
            return "Vision stage was not run; body metrics need a visible person."
        return "Vision stage was not run; gaze metrics need a visible face."
    if category_id == "visual_aids":
        return "Vision and slides stages were not run (Phase 1 is audio/text only)."
    return "Required video evidence is not available."
