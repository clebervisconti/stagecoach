"""vision_quality.json and declared-vs-detected camera setup (issue #39, SPEC §6.5)."""

from __future__ import annotations

from typing import Any, Optional

import numpy as np

SETUP_LABELS = ("stage", "to_camera", "screen_recording", "audio_only", "unknown")


def detect_setup(
    *,
    person_visible_ratio: float,
    face_visible_ratio: float,
    mean_face_height_px: float,
    mean_person_height_norm: float,
    has_video: bool,
) -> str:
    """Heuristic (H): face size and person presence vs declared camera setup."""
    if not has_video or person_visible_ratio < 0.08:
        return "screen_recording" if has_video else "audio_only"
    # Head-and-shoulders (webcam) fills ~35%+ of frame height with a large face (H).
    if mean_face_height_px >= 80 and mean_person_height_norm >= 0.35:
        return "to_camera"
    return "stage"


def mismatch_scale(declared: str, detected: str) -> tuple[bool, Optional[str], float]:
    """Warning + threshold scale when declared setup disagrees with detection."""
    declared = declared if declared in SETUP_LABELS else "unknown"
    if declared in {"unknown", detected}:
        return False, None, 1.0
    if declared == "audio_only":
        return True, "Declared audio-only but video landmarks were detected.", 1.0
    if declared in {"stage", "to_camera"} and detected == "screen_recording":
        return (
            True,
            "Declared a person-facing camera but almost no person was visible; event thresholds were relaxed.",
            1.8,
        )
    if declared == "screen_recording" and detected in {"stage", "to_camera"}:
        return (
            True,
            "Declared a screen recording but a person was visible; event thresholds follow the detected person framing.",
            1.0,
        )
    if declared == "to_camera" and detected == "stage":
        return (
            True,
            "Declared to-camera framing but the face is small (stage-like). Gaze and expression gates are looser.",
            1.35,
        )
    if declared == "stage" and detected == "to_camera":
        return (
            True,
            "Declared a stage camera but the face fills the frame (to-camera). Notes-down and screen-turn bands tighten.",
            0.85,
        )
    return True, f"Declared {declared} but detected {detected}.", 1.2


def build_quality(
    pose_rows: list[dict[str, Any]],
    face_rows: list[dict[str, Any]],
    frames_meta: list[Any],
    *,
    declared_setup: str,
    has_video: bool,
    frame_height: int = 480,
) -> dict[str, Any]:
    person_vis = [float(r.get("person_visible") or 0.0) for r in pose_rows] or [0.0]
    face_vis = [float(r.get("face_visible") or 0.0) for r in face_rows] or [0.0]
    face_h = [float(r.get("face_height_px") or 0.0) for r in face_rows if r.get("face_visible")]
    person_h = []
    for r in pose_rows:
        bh = r.get("bbox_h")
        if bh is not None and not (isinstance(bh, float) and np.isnan(bh)):
            person_h.append(float(bh))
    lumas = [f.luma for f in frames_meta if getattr(f, "luma", None) is not None]
    motions = [f.motion for f in frames_meta if getattr(f, "motion", None) is not None]
    vis_mean = [float(r.get("visibility_mean") or 0.0) for r in pose_rows if r.get("person_visible")]
    occlusion = 0.0
    if vis_mean:
        occlusion = float(np.mean([1.0 if v < 0.5 else 0.0 for v in vis_mean]))

    person_ratio = float(np.mean(person_vis))
    face_ratio = float(np.mean(face_vis)) if face_rows else 0.0
    mean_face_px = float(np.mean(face_h)) if face_h else 0.0
    mean_person_norm = float(np.mean(person_h)) if person_h else 0.0
    detected = detect_setup(
        person_visible_ratio=person_ratio,
        face_visible_ratio=face_ratio,
        mean_face_height_px=mean_face_px,
        mean_person_height_norm=mean_person_norm,
        has_video=has_video,
    )
    mismatched, warning, scale = mismatch_scale(declared_setup, detected)
    return {
        "person_visible_ratio": round(person_ratio, 4),
        "face_visible_ratio": round(face_ratio, 4),
        "mean_face_height_px": round(mean_face_px, 2),
        "mean_person_height_px": round(mean_person_norm * frame_height, 2),
        "mean_luma": round(float(np.mean(lumas)), 4) if lumas else None,
        "camera_motion": round(float(np.mean(motions)), 4) if motions else None,
        "occlusion_ratio": round(occlusion, 4),
        "camera_setup": {
            "declared": declared_setup,
            "detected": detected,
            "mismatch": mismatched,
            "warning": warning,
            "threshold_scale": scale,
        },
        "emotion_inference": False,
    }
