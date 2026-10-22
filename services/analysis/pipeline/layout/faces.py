"""Face boxes for layout detection (spec §9.2, ADR-062).

YuNet (MIT, OpenCV FaceDetectorYN) is the production detector. Tests inject
`FakeFaceDetector` with scripted boxes so CI never needs a personal face.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import numpy as np

from pipeline.vision.models import MODEL_REGISTRY, default_models_dir, ensure_models

YUNET_SCORE_MIN = 0.70
YUNET_FILENAME = "face_detection_yunet_2023mar.onnx"


@dataclass(frozen=True)
class FaceDetection:
    """Axis-aligned box plus optional 5 landmarks, in pixel coordinates."""

    x: float
    y: float
    w: float
    h: float
    score: float
    landmarks: list[tuple[float, float]] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "x": self.x,
            "y": self.y,
            "w": self.w,
            "h": self.h,
            "score": self.score,
            "landmarks": [list(point) for point in self.landmarks],
        }


class FaceDetector(Protocol):
    def detect(self, frame_bgr: np.ndarray) -> list[FaceDetection]:
        """Return faces in a BGR frame. Never logs or stores pixels."""


class FakeFaceDetector:
    """Scripted boxes for unit and golden tests. Mirrors vision/synthetic.py."""

    def __init__(self, detections: list[FaceDetection] | None = None) -> None:
        self.detections = list(detections or [])

    def detect(self, frame_bgr: np.ndarray) -> list[FaceDetection]:
        _ = frame_bgr
        return list(self.detections)


def yunet_registry_row() -> dict:
    for row in MODEL_REGISTRY:
        if row.get("model_name") == "face_detection_yunet_2023mar":
            return row
    raise KeyError("YuNet is not registered in MODEL_REGISTRY")


def ensure_yunet_model(models_dir: Path | None = None) -> Path:
    paths = ensure_models(models_dir, components={"layout_face"}, include_layout=True)
    return paths[YUNET_FILENAME]


class YuNetFaceDetector:
    """OpenCV FaceDetectorYN wrapper. Static-shape 2023mar model (S66)."""

    def __init__(self, model_path: Path | None = None) -> None:
        self.model_path = Path(model_path) if model_path is not None else default_models_dir() / YUNET_FILENAME
        self._detector = None
        self._input_size: tuple[int, int] | None = None

    def _ensure(self, width: int, height: int) -> None:
        import cv2

        if self._detector is None:
            if not self.model_path.is_file():
                self.model_path = ensure_yunet_model(self.model_path.parent)
            self._detector = cv2.FaceDetectorYN.create(
                str(self.model_path),
                "",
                (width, height),
                YUNET_SCORE_MIN,
                0.3,
                5000,
            )
            self._input_size = (width, height)
            return
        if self._input_size != (width, height):
            self._detector.setInputSize((width, height))
            self._input_size = (width, height)

    def detect(self, frame_bgr: np.ndarray) -> list[FaceDetection]:
        if frame_bgr is None or frame_bgr.size == 0:
            return []
        height, width = frame_bgr.shape[:2]
        self._ensure(int(width), int(height))
        _retval, faces = self._detector.detect(frame_bgr)
        if faces is None:
            return []
        out: list[FaceDetection] = []
        for row in faces:
            score = float(row[14]) if len(row) > 14 else float(row[-1])
            if score < YUNET_SCORE_MIN:
                continue
            landmarks = [
                (float(row[4]), float(row[5])),
                (float(row[6]), float(row[7])),
                (float(row[8]), float(row[9])),
                (float(row[10]), float(row[11])),
                (float(row[12]), float(row[13])),
            ]
            out.append(
                FaceDetection(
                    x=float(row[0]),
                    y=float(row[1]),
                    w=float(row[2]),
                    h=float(row[3]),
                    score=score,
                    landmarks=landmarks,
                )
            )
        return out
