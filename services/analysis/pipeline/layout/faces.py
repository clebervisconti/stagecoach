"""Face boxes for layout detection (spec §9.2, ADR-062).

YuNet (MIT, OpenCV FaceDetectorYN) is the production detector. The worker
image bakes the ONNX file into /models (ADR-075). Tests inject
`FakeFaceDetector` with scripted boxes so unit tests never need a personal
face. The composite fixture uses a generated CC0 face for the real YuNet path.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, Protocol

import numpy as np

from pipeline.vision.models import MODEL_REGISTRY, default_models_dir, ensure_models

YUNET_SCORE_MIN = 0.70
YUNET_FILENAME = "face_detection_yunet_2023mar.onnx"
# 2023mar is trained at 320×320; faces of about 10–300 px (ADR-062 / S66).
YUNET_MIN_SIDE = 320


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


def letterbox_to_min_side(
    frame_bgr: np.ndarray, min_side: int = YUNET_MIN_SIDE
) -> tuple[np.ndarray, int, int]:
    """Pad (not stretch) so both sides are at least `min_side`."""
    height, width = frame_bgr.shape[:2]
    pad_x = max(0, min_side - width)
    pad_y = max(0, min_side - height)
    if pad_x == 0 and pad_y == 0:
        return frame_bgr, 0, 0
    import cv2

    top = pad_y // 2
    left = pad_x // 2
    padded = cv2.copyMakeBorder(
        frame_bgr,
        top,
        pad_y - top,
        left,
        pad_x - left,
        cv2.BORDER_CONSTANT,
        value=(0, 0, 0),
    )
    return padded, left, top


def prepare_for_yunet(
    frame_bgr: np.ndarray, min_side: int = YUNET_MIN_SIDE
) -> tuple[np.ndarray, float, float, int, int]:
    """Fit a frame into YuNet's 10–300 px face band and ≥320 input.

    A 320×240 1080p PiP crop is already in-band (face ~240 px). Stretching
    that crop to 960 px makes the face ~700 px and YuNet returns nothing
    (LION O1 round 3). A 106×78 crop from a 640×360 test clip is too
    small: upscale so the short side is 320, then map boxes back.
    """
    height, width = frame_bgr.shape[:2]
    if min(width, height) < min_side:
        import cv2

        scale = min_side / min(width, height)
        new_w = max(2, int(round(width * scale)))
        new_h = max(2, int(round(height * scale)))
        resized = cv2.resize(frame_bgr, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        return resized, scale, scale, 0, 0
    padded, origin_x, origin_y = letterbox_to_min_side(frame_bgr, min_side)
    return padded, 1.0, 1.0, origin_x, origin_y


@contextlib.contextmanager
def _opencv_quiet_yunet_dnn() -> Iterator[None]:
    """Drop the OpenCV 5.0.0 YuNet target warning around create/setInputSize.

    The only cv2.dnn net this worker constructs is FaceDetectorYN (YuNet
    2023mar ONNX). A repo-wide search finds no readNet, DetectionModel, or
    FaceRecognizerSF. FaceDetectorYN.create still calls setPreferableTarget
    internally. On OpenCV 5.0.0 that logs "setPreferableTarget Targets are
    not supported" even when backend=DNN_BACKEND_OPENCV and
    target=DNN_TARGET_CPU, because the ONNX NMS node cannot be assigned a
    target in that build. Inference still runs on CPU. The message is a
    C++ CV_LOG_WARNING (stderr), not a Python warnings.warn, so
    warnings.filterwarnings cannot hide it. Quiet the OpenCV logger only
    for these two calls.
    """
    import cv2

    utils = getattr(getattr(cv2, "utils", None), "logging", None)
    if utils is None or not hasattr(utils, "setLogLevel"):
        yield
        return
    previous = utils.getLogLevel()
    utils.setLogLevel(utils.LOG_LEVEL_ERROR)
    try:
        yield
    finally:
        utils.setLogLevel(previous)


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
            # OpenCV warns "setPreferableTarget Targets are not supported" when
            # FaceDetectorYN picks a default (often OpenCL) the build cannot use.
            # Pin CPU, then quiet the leftover OpenCV 5 NMS-target warning.
            with _opencv_quiet_yunet_dnn():
                self._detector = cv2.FaceDetectorYN.create(
                    str(self.model_path),
                    "",
                    (width, height),
                    YUNET_SCORE_MIN,
                    0.3,
                    5000,
                    cv2.dnn.DNN_BACKEND_OPENCV,
                    cv2.dnn.DNN_TARGET_CPU,
                )
            self._input_size = (width, height)
            return
        if self._input_size != (width, height):
            with _opencv_quiet_yunet_dnn():
                self._detector.setInputSize((width, height))
            self._input_size = (width, height)

    def detect(self, frame_bgr: np.ndarray) -> list[FaceDetection]:
        if frame_bgr is None or frame_bgr.size == 0:
            return []
        prepared, scale_x, scale_y, origin_x, origin_y = prepare_for_yunet(frame_bgr)
        height, width = prepared.shape[:2]
        self._ensure(int(width), int(height))
        _retval, faces = self._detector.detect(prepared)
        if faces is None:
            return []
        out: list[FaceDetection] = []
        for row in faces:
            score = float(row[14]) if len(row) > 14 else float(row[-1])
            if score < YUNET_SCORE_MIN:
                continue
            landmarks = [
                ((float(row[4]) - origin_x) / scale_x, (float(row[5]) - origin_y) / scale_y),
                ((float(row[6]) - origin_x) / scale_x, (float(row[7]) - origin_y) / scale_y),
                ((float(row[8]) - origin_x) / scale_x, (float(row[9]) - origin_y) / scale_y),
                ((float(row[10]) - origin_x) / scale_x, (float(row[11]) - origin_y) / scale_y),
                ((float(row[12]) - origin_x) / scale_x, (float(row[13]) - origin_y) / scale_y),
            ]
            out.append(
                FaceDetection(
                    x=(float(row[0]) - origin_x) / scale_x,
                    y=(float(row[1]) - origin_y) / scale_y,
                    w=float(row[2]) / scale_x,
                    h=float(row[3]) / scale_y,
                    score=score,
                    landmarks=landmarks,
                )
            )
        return out
