"""Online layout detection (Phase O0+). Face boxes only; no landmarks to LLMs."""

from pipeline.layout.crop import write_region_tracks
from pipeline.layout.detect import detect_layout
from pipeline.layout.faces import FaceDetection, FaceDetector, FakeFaceDetector, YuNetFaceDetector
from pipeline.layout.review import needs_layout_review

__all__ = [
    "FaceDetection",
    "FaceDetector",
    "FakeFaceDetector",
    "YuNetFaceDetector",
    "detect_layout",
    "needs_layout_review",
    "write_region_tracks",
]
