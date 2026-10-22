"""YuNet face-visible ratio on a camera crop or sampled detections.

MediaPipe face landmarks often miss the generated composite face (no body,
cartoon landmarks). Layout already found the camera tile with YuNet. Measuring
that same detector on `camera.mp4` is what the report should publish.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from pipeline.layout.faces import FaceDetection, FaceDetector, YuNetFaceDetector
from pipeline.layout.sampling import sample_frames

CAMERA_FACE_QUALITY = "camera_face_quality.json"


def ratio_from_detections(detections: list[list[FaceDetection]]) -> float:
    if not detections:
        return 0.0
    hits = sum(1 for row in detections if row)
    return round(hits / len(detections), 4)


def measure_face_visible_ratio(
    video_path: Path,
    *,
    detector: Optional[FaceDetector] = None,
    max_frames: int = 8,
    fps: float = 1.0,
) -> dict[str, Any]:
    """Sample `video_path` and return YuNet face-visible ratio."""
    frames = sample_frames(video_path, fps=fps, max_frames=max_frames)
    if detector is None:
        detector = YuNetFaceDetector()
    detections = [detector.detect(frame.bgr) for frame in frames]
    hits = sum(1 for row in detections if row)
    n = len(frames)
    return {
        "face_visible_ratio": round(hits / n, 4) if n else 0.0,
        "frames_sampled": n,
        "frames_with_face": hits,
        "source": "yunet_camera_crop",
    }


def write_camera_face_quality(
    camera_path: Path,
    output_dir: Path,
    *,
    detector: Optional[FaceDetector] = None,
) -> Optional[dict[str, Any]]:
    if not camera_path.is_file():
        return None
    payload = measure_face_visible_ratio(camera_path, detector=detector)
    dest = output_dir / CAMERA_FACE_QUALITY
    dest.write_text(json.dumps(payload, indent=2) + "\n")
    return payload
