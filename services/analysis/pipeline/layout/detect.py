"""Single-layout detection for O1 (composite / camera_full / screen_full)."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

import numpy as np

from pipeline.layout.faces import FaceDetection, FaceDetector, FakeFaceDetector, YuNetFaceDetector
from pipeline.layout.review import needs_layout_review
from pipeline.layout.sampling import extract_preview_jpeg, sample_frames
from pipeline.layout.tiles import fallback_tile, grow_tile, iou, screen_in_complement

logger = logging.getLogger(__name__)

DETECTOR_VERSION = "1.0.0"
LAYOUT_VERSION = 1
FACE_FULL_RATIO = 0.12
LUMA_BLACK = 8.0


def _mean_luma(frames) -> float:
    if not frames:
        return 0.0
    return float(np.mean([float(np.mean(frame.gray)) for frame in frames[: min(8, len(frames))]]))


def _edge_density(gray: np.ndarray) -> float:
    import cv2

    edges = cv2.Canny(gray, 50, 150)
    return float(np.mean(edges > 0))


def _stable_face(detections: list[list[FaceDetection]]) -> Optional[FaceDetection]:
    present = [row[0] for row in detections if row]
    if not present:
        return None
    ratio = len(present) / max(1, len(detections))
    if ratio < 0.60:
        return None
    xs = [face.x + face.w / 2 for face in present]
    if len(xs) >= 2:
        width = max(face.x + face.w for face in present) or 1.0
        if float(np.std(xs)) > 0.02 * width and ratio < 0.85:
            return None
    # Median box
    return FaceDetection(
        x=float(np.median([f.x for f in present])),
        y=float(np.median([f.y for f in present])),
        w=float(np.median([f.w for f in present])),
        h=float(np.median([f.h for f in present])),
        score=float(np.median([f.score for f in present])),
    )


def _region(role: str, box: tuple[float, float, float, float], confidence: float, index: int) -> dict[str, Any]:
    x, y, w, h = box
    return {
        "id": f"r{index}",
        "role": role,
        "x": round(x, 4),
        "y": round(y, 4),
        "w": round(w, 4),
        "h": round(h, 4),
        "confidence": round(confidence, 3),
        "source": "auto",
    }


def detect_layout(
    video_path: Path,
    output_dir: Path,
    *,
    duration_s: float,
    frame_width: int,
    frame_height: int,
    delivery_mode: str = "webinar",
    detector: Optional[FaceDetector] = None,
    preview_source: Optional[Path] = None,
) -> dict[str, Any]:
    """Write layout.json + a private preview JPEG. Single segment in O1."""
    output_dir.mkdir(parents=True, exist_ok=True)
    preview_dir = output_dir / "layout_preview"
    preview_dir.mkdir(parents=True, exist_ok=True)

    review_reason: Optional[str] = None
    frames = []
    detections: list[list[FaceDetection]] = []
    try:
        frames = sample_frames(video_path)
        if detector is None:
            detector = YuNetFaceDetector()
        for frame in frames:
            detections.append(detector.detect(frame.bgr))
    except Exception as exc:
        logger.warning("layout detector failed: %s", exc)
        review_reason = "no_regions_found"
        frames = []
        detections = []

    face = _stable_face(detections) if detections else None
    luma = _mean_luma(frames)
    edges = _edge_density(frames[len(frames) // 2].gray) if frames else 0.0
    kind = "no_video"
    camera_box: Optional[tuple[float, float, float, float]] = None
    screen_box: Optional[tuple[float, float, float, float]] = None
    ignore_boxes: list[tuple[float, float, float, float]] = []
    confidence = 0.35

    if luma < LUMA_BLACK and not face:
        kind = "no_video"
        review_reason = review_reason or "no_regions_found"
        confidence = 0.2
    elif face is None:
        kind = "screen_full"
        screen_box = (0.0, 0.0, 1.0, 1.0)
        confidence = 0.86 if edges >= 0.01 or luma >= 12 else 0.55
        if confidence < 0.80:
            review_reason = review_reason or "screen_region_unclear"
    else:
        sample = frames[0] if frames else None
        fh = face.h / frame_height if frame_height else 0
        if sample is not None:
            # Face coords are in the sampled frame (960-wide). Convert to 0–1 via sample size.
            sh, sw = sample.bgr.shape[:2]
            face_ratio = face.h / sh
            if face_ratio >= FACE_FULL_RATIO:
                kind = "camera_full"
                camera_box = (0.0, 0.0, 1.0, 1.0)
                confidence = 0.90
            else:
                kind = "composite"
                grown = grow_tile(sample.bgr, face)
                if grown[2] * grown[3] < 0.02:
                    grown = fallback_tile(face, sw, sh)
                camera_box = grown
                screen_box = screen_in_complement(camera_box)
                # Residual strip below/beside a PiP is ignored when small.
                if camera_box[1] + camera_box[3] < 0.95:
                    leftover_h = 1.0 - (camera_box[1] + camera_box[3])
                    if leftover_h >= 0.05 and camera_box[0] > 0.5:
                        ignore_boxes.append((camera_box[0], camera_box[1] + camera_box[3], camera_box[2], leftover_h))
                tile_conf = 0.92 if iou(camera_box, camera_box) >= 0.5 else 0.7
                confidence = float(min(0.95, max(0.55, tile_conf * (0.7 + 0.3 * face.score))))
                if confidence < 0.80:
                    review_reason = review_reason or "camera_tile_low_confidence"
        else:
            kind = "camera_full" if fh >= FACE_FULL_RATIO else "composite"
            camera_box = (0.0, 0.0, 1.0, 1.0) if kind == "camera_full" else fallback_tile(
                face, frame_width, frame_height
            )
            if kind == "composite":
                screen_box = screen_in_complement(camera_box)
            confidence = 0.7
            review_reason = review_reason or "camera_tile_low_confidence"

    if delivery_mode == "stage" and kind == "composite":
        kind = "stage_wide"

    if frame_height and frame_height < 360:
        confidence = min(confidence, confidence * 0.8)

    regions: list[dict[str, Any]] = []
    if camera_box:
        regions.append(_region("camera", camera_box, confidence, len(regions)))
    if screen_box:
        regions.append(_region("screen", screen_box, min(0.95, confidence + 0.04), len(regions)))
    for box in ignore_boxes:
        regions.append(_region("ignore", box, 0.7, len(regions)))

    if not regions:
        review_reason = "no_regions_found"
        kind = "no_video"
        confidence = min(confidence, 0.35)

    t_end = max(duration_s, frames[-1].t if frames else duration_s)
    segment = {
        "index": 0,
        "t_start": 0.0,
        "t_end": float(t_end),
        "kind": kind,
        "confidence": round(confidence, 3),
        "regions": regions,
    }
    preview_t = min(max(t_end * 0.22, 0.0), max(t_end - 0.05, 0.0))
    preview_path = preview_dir / "segment_000.jpg"
    source = preview_source or video_path
    try:
        extract_preview_jpeg(source, preview_path, t=preview_t)
    except Exception as exc:
        logger.warning("layout preview failed: %s", exc)

    payload = {
        "version": LAYOUT_VERSION,
        "detector_version": DETECTOR_VERSION,
        "status": "detected",
        "confidence": round(confidence, 3),
        "review_reason": review_reason,
        "frame": {
            "width": int(frame_width),
            "height": int(frame_height),
            "duration_s": float(duration_s),
        },
        "analysis_window": None,
        "sync": None,
        "preview_t": preview_t,
        "segments": [segment],
    }
    dest = output_dir / "layout.json"
    dest.write_text(json.dumps(payload, indent=2) + "\n")
    return payload


def decide_review(layout: dict[str, Any], *, pref: str, confirmed_count: int) -> bool:
    segs = [float(seg.get("confidence") or 0) for seg in layout.get("segments") or []]
    return needs_layout_review(
        pref=pref,
        confirmed_count=confirmed_count,
        confidence=float(layout.get("confidence") or 0),
        segment_confidences=segs,
        review_reason=layout.get("review_reason"),
        n_segments=len(layout.get("segments") or []),
    )


# Re-export for tests that inject a scripted detector.
FakeFaceDetector = FakeFaceDetector
