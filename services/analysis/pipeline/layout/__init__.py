"""Online layout detection (Phase O0+). Face boxes only; no landmarks to LLMs."""

from pipeline.layout.faces import FaceDetection, FaceDetector, FakeFaceDetector, YuNetFaceDetector

__all__ = [
    "FaceDetection",
    "FaceDetector",
    "FakeFaceDetector",
    "YuNetFaceDetector",
]
