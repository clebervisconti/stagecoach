"""Category 14 facial-expressiveness metrics from blendshapes (issue #42, D8).

Observable movement and variability only. No emotion labels, no affect
classification, no SER. Requires expression_analysis.
"""

from __future__ import annotations

from typing import Any, Optional

import numpy as np

from pipeline.vision.features import BLENDSHAPE_SUBSET

SMILE_THRESH = 0.4  # H, SPEC §4.4.14
WINDOW_S = 5.0
VARIETY_THRESH = 0.3
SERIOUS_CUES = ("layoff", "laid off", "outage", "incident report", "fatality")
CELEBRATORY_CUES = ("congratulat", "anniversary celebration")


def _blendshape_vector(blendshapes: dict[str, float]) -> np.ndarray:
    return np.asarray([float(blendshapes.get(name, 0.0)) for name in BLENDSHAPE_SUBSET], dtype=np.float64)


def _smile(blendshapes: dict[str, float]) -> float:
    return (
        float(blendshapes.get("mouthSmileLeft", 0.0)) + float(blendshapes.get("mouthSmileRight", 0.0))
    ) / 2.0


def _windows(times: np.ndarray, values: np.ndarray, width: float) -> list[float]:
    if times.size == 0:
        return []
    out: list[float] = []
    t0 = float(times[0])
    t1 = float(times[-1])
    start = t0
    while start < t1:
        end = start + width
        mask = (times >= start) & (times < end)
        if np.any(mask):
            out.append(float(np.std(values[mask])))
        start = end
    return out


def _incongruence_flags(
    events: list[dict[str, Any]],
    transcript: Optional[dict[str, Any]],
    duration_s: float,
) -> tuple[float, list[dict[str, Any]]]:
    """Count smile/flat-face overlaps with transcript cue phrases. Heuristic (H).

    Labels the *content* of a sentence, not a face state. Observations only.
    """
    observations: list[dict[str, Any]] = []
    if not transcript:
        return 0.0, observations
    segments = transcript.get("segments") or []
    smiles = [e for e in events if e.get("type") == "smile" and (e.get("t_end", 0) - e.get("t_start", 0)) >= 2.0]
    flats = [e for e in events if e.get("type") == "flat_face"]
    for seg in segments:
        text = str(seg.get("text") or "").lower()
        t0 = float(seg.get("start") or 0.0)
        t1 = float(seg.get("end") or t0)
        serious = any(cue in text for cue in SERIOUS_CUES)
        celebratory = any(cue in text for cue in CELEBRATORY_CUES)
        if serious:
            for ev in smiles:
                if ev["t_start"] < t1 and ev["t_end"] > t0:
                    observations.append(
                        {
                            "t_start": ev["t_start"],
                            "t_end": ev["t_end"],
                            "note": "Smile signal overlapped a sentence with a serious content cue. Review as an observation.",
                        }
                    )
        if celebratory:
            for ev in flats:
                if ev["t_start"] < t1 and ev["t_end"] > t0:
                    observations.append(
                        {
                            "t_start": ev["t_start"],
                            "t_end": ev["t_end"],
                            "note": "Low facial movement overlapped a celebratory content cue. Review as an observation.",
                        }
                    )
    per_10 = len(observations) * (600.0 / max(duration_s, 1.0))
    return per_10, observations


def compute_expression_metrics(
    face_rows: list[dict[str, Any]],
    events: list[dict[str, Any]],
    *,
    duration_s: float,
    transcript: Optional[dict[str, Any]] = None,
) -> Optional[dict[str, Any]]:
    """Return scoring-config v1.0.0 facial_affect metric values, or None."""
    visible = [row for row in face_rows if row.get("face_visible") and (row.get("blendshapes") or {})]
    if not visible:
        return None
    times = np.asarray([float(row["t"]) for row in visible], dtype=np.float64)
    smiles = np.asarray([_smile(row.get("blendshapes") or {}) for row in visible], dtype=np.float64)
    vectors = np.stack([_blendshape_vector(row.get("blendshapes") or {}) for row in visible], axis=0)
    per_frame_sd = np.std(vectors, axis=1)
    window_sds = _windows(times, per_frame_sd, WINDOW_S)
    expressivity = float(np.mean(window_sds)) if window_sds else float(np.mean(per_frame_sd))
    smile_ratio = float(np.mean(smiles > SMILE_THRESH))
    peaks = np.max(vectors, axis=0)
    variety = int(np.sum(peaks > VARIETY_THRESH))
    face_h = [float(row.get("face_height_px") or 0.0) for row in visible]
    payload = {
        "emotion_inference": False,
        "face_visible_ratio": round(len(visible) / max(len(face_rows), 1), 4),
        "face_px_median": round(float(np.median(face_h)) if face_h else 0.0, 2),
        "metrics": {
            "fa_smile_presence_ratio": {
                "value": round(smile_ratio, 4),
                "confidence": 0.7,
                "applicable": True,
            },
            "fa_expressivity_index": {
                "value": round(expressivity, 4),
                "confidence": 0.7,
                "applicable": True,
            },
            "fa_expression_variety": {
                "value": float(variety),
                "confidence": 0.65,
                "applicable": True,
            },
            "fa_congruence": {
                "value": None,
                "confidence": 0.4,
                "applicable": False,
                "incongruence_flags_per_10min": 0.0,
                "observations": [],
            },
        },
        "flat_face_count": sum(1 for e in events if e.get("type") == "flat_face"),
        "smile_event_count": sum(1 for e in events if e.get("type") == "smile"),
    }
    return attach_incongruence(payload, events, transcript, duration_s)


def attach_incongruence(
    payload: dict[str, Any],
    events: list[dict[str, Any]],
    transcript: Optional[dict[str, Any]],
    duration_s: float,
) -> dict[str, Any]:
    """Fill fa_congruence from transcript cues after ASR. Still not emotion inference."""
    flags_per_10, observations = _incongruence_flags(events, transcript, duration_s)
    if transcript is None:
        level = None
    elif flags_per_10 <= 0:
        level = 5.0
    elif flags_per_10 < 1:
        level = 4.0
    elif flags_per_10 < 3:
        level = 3.0
    else:
        level = 2.0
    row = payload.setdefault("metrics", {}).setdefault("fa_congruence", {})
    row["value"] = level
    row["confidence"] = 0.4
    row["applicable"] = level is not None
    row["incongruence_flags_per_10min"] = round(flags_per_10, 4)
    row["observations"] = observations
    return payload
