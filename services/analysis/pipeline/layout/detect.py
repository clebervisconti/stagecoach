"""Single-layout detection for O1 (composite / camera_full / screen_full)."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

import numpy as np

from pipeline.layout.face_visibility import ratio_from_detections
from pipeline.layout.faces import FaceDetection, FaceDetector, FakeFaceDetector, YuNetFaceDetector
from pipeline.layout.review import needs_layout_review
from pipeline.layout.sampling import extract_preview_jpeg, sample_frames
from pipeline.layout.switching import mark_from_faces, stable_runs
from pipeline.layout.tiles import fallback_tile, grow_tile, iou, screen_in_complement

logger = logging.getLogger(__name__)

DETECTOR_VERSION = "1.0.0"
LAYOUT_VERSION = 1
# PiP tiles sit around 0.15–0.22 of frame height; a full-frame face is larger.
FACE_FULL_RATIO = 0.28
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


def _norm_face(face: FaceDetection, width: int, height: int) -> tuple[float, float, float, float]:
    x = face.x / width if width else 0.0
    y = face.y / height if height else 0.0
    w = max(face.w / width if width else 0.0, 0.05)
    h = max(face.h / height if height else 0.0, 0.05)
    if x + w > 1:
        x = max(0.0, 1.0 - w)
    if y + h > 1:
        y = max(0.0, 1.0 - h)
    return (x, y, w, h)


def _gallery_regions(
    detections: list[list[FaceDetection]],
    frames,
) -> Optional[tuple[str, list[dict[str, Any]], float, Optional[str]]]:
    """Several spread-out faces: one camera tile, the rest other participants."""
    counts = [len(row) for row in detections]
    if not counts or float(np.median(counts)) < 3 or not frames:
        return None
    best_index = max(range(len(detections)), key=lambda index: len(detections[index]))
    faces = detections[best_index]
    sample = frames[min(best_index, len(frames) - 1)]
    height, width = sample.bgr.shape[:2]
    if not _faces_spread(faces, width, height):
        return None
    ranked = sorted(faces, key=lambda face: face.score, reverse=True)[:8]
    regions: list[dict[str, Any]] = []
    for index, face in enumerate(ranked):
        role = "camera" if index == 0 else "other_participant"
        regions.append(_region(role, _norm_face(face, width, height), float(face.score), len(regions)))
    scores = [face.score for face in ranked[:2]]
    unclear = len(scores) > 1 and abs(scores[0] - scores[1]) < 0.1
    reason = "primary_speaker_unclear" if unclear else None
    confidence = float(min(0.9, max(0.55, ranked[0].score)))
    return ("gallery", regions, confidence, reason)


def _faces_spread(faces: list[FaceDetection], width: int, height: int) -> bool:
    if width <= 0 or height <= 0 or len(faces) < 3:
        return False
    xs = [(face.x + face.w / 2) / width for face in faces]
    ys = [(face.y + face.h / 2) / height for face in faces]
    return (max(xs) - min(xs)) >= 0.25 or (max(ys) - min(ys)) >= 0.25


def _classify_frames(
    frames,
    detections: list[list[FaceDetection]],
    *,
    frame_width: int,
    frame_height: int,
    delivery_mode: str,
    review_reason: Optional[str],
) -> tuple[str, list[dict[str, Any]], float, Optional[str]]:
    gallery = _gallery_regions(detections, frames)
    if gallery and (not review_reason or review_reason == "no_regions_found"):
        return _cap_resolution(gallery, frame_height)

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
    return _cap_resolution((kind, regions, confidence, review_reason), frame_height)


def _cap_resolution(
    classified: tuple[str, list[dict[str, Any]], float, Optional[str]],
    frame_height: int,
) -> tuple[str, list[dict[str, Any]], float, Optional[str]]:
    kind, regions, confidence, reason = classified
    if frame_height and frame_height < 360:
        confidence = min(confidence, confidence * 0.8)
    return kind, regions, confidence, reason


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
    """Write layout.json and one preview JPEG per stable layout run."""
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

    marks = []
    if frames and len(frames) == len(detections):
        sample_h, sample_w = frames[0].bgr.shape[:2]
        marks = [mark_from_faces(frame.t, row, sample_w, sample_h) for frame, row in zip(frames, detections)]
    runs = stable_runs(marks)
    source = preview_source or video_path
    t_end = max(duration_s, frames[-1].t if frames else duration_s)
    segments: list[dict[str, Any]] = []
    if len(runs) > 1:
        step = (marks[1].t - marks[0].t) if len(marks) > 1 else 2.0
        run_reasons: list[str] = []
        for index, (begin, end) in enumerate(runs):
            kind, regions, run_confidence, run_reason = _classify_frames(
                frames[begin:end],
                detections[begin:end],
                frame_width=frame_width,
                frame_height=frame_height,
                delivery_mode=delivery_mode,
                review_reason=None,
            )
            for region_index, region in enumerate(regions):
                region["id"] = f"s{index}r{region_index}"
            if run_reason:
                run_reasons.append(run_reason)
            start = 0.0 if index == 0 else float(marks[begin].t)
            stop = float(t_end) if index == len(runs) - 1 else float(marks[end - 1].t + step)
            segments.append(
                {
                    "index": index,
                    "t_start": round(start, 3),
                    "t_end": round(stop, 3),
                    "kind": kind,
                    "confidence": round(run_confidence, 3),
                    "regions": regions,
                }
            )
        for index, segment in enumerate(segments[:-1]):
            segment["t_end"] = segments[index + 1]["t_start"]
        confidence = min(float(segment["confidence"]) for segment in segments)
        if not review_reason and run_reasons:
            review_reason = run_reasons[0]
        if len(segments) > 6:
            review_reason = review_reason or "many_layout_changes"
    else:
        kind, regions, confidence, review_reason = _classify_frames(
            frames,
            detections,
            frame_width=frame_width,
            frame_height=frame_height,
            delivery_mode=delivery_mode,
            review_reason=review_reason,
        )
        segments = [
            {
                "index": 0,
                "t_start": 0.0,
                "t_end": float(t_end),
                "kind": kind,
                "confidence": round(confidence, 3),
                "regions": regions,
            }
        ]

    preview_t = min(max(float(t_end) * 0.22, 0.0), max(float(t_end) - 0.05, 0.0))
    for segment in segments:
        preview_path = preview_dir / f"segment_{int(segment['index']):03d}.jpg"
        midpoint = (float(segment["t_start"]) + float(segment["t_end"])) / 2
        try:
            extract_preview_jpeg(source, preview_path, t=midpoint if len(segments) > 1 else preview_t)
        except Exception as exc:
            logger.warning("layout preview failed: %s", exc)

    payload = {
        "version": LAYOUT_VERSION,
        "detector_version": DETECTOR_VERSION,
        "status": "detected",
        "confidence": round(confidence, 3),
        "review_reason": review_reason,
        "face_visible_ratio": ratio_from_detections(detections),
        "frame": {
            "width": int(frame_width),
            "height": int(frame_height),
            "duration_s": float(duration_s),
        },
        "analysis_window": None,
        "sync": None,
        "preview_t": preview_t,
        "segments": segments,
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
