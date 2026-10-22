# ADR-062: Layout detection with YuNet and a fake detector

**Date:** 2026-10-22  
**Status:** Accepted  
**Phase:** O0  
**Owner decision:** OD-4 (a) applies from O1; this ADR records the detector choice

## Context

Composite recordings need a face box to find the camera tile. MediaPipe landmarks stay consent-gated. Layout only needs rectangles.

## Decision

- Face boxes come from **YuNet** (OpenCV Zoo, `cv2.FaceDetectorYN`, ONNX).
- Licence: **MIT**. Evidence: https://github.com/opencv/opencv_zoo/blob/main/models/face_detection_yunet/LICENSE (S66). The model file is not vendored in this public repo.
- Pin: `face_detection_yunet_2023mar.onnx`, SHA-256 `8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4`, downloaded 22 Oct 2026 from the OpenCV Zoo main branch.
- `pipeline/layout/faces.py` defines a `FaceDetector` protocol, `YuNetFaceDetector`, and `FakeFaceDetector` (scripted boxes for tests).
- Full layout segmentation, review, and crops wait for O1. O0 only lands the registry and the detector protocol.

## Alternatives considered

1. **MediaPipe face landmarker for layout** — rejected. Landmarks are consent-gated (ADR-024) and heavier than boxes.  
2. **Haar cascade** — rejected. Worse on small tiles; YuNet is documented for 10–300 px faces.

## Consequences

- Tests never require a personal face. `FakeFaceDetector` covers unit tests. A `@pytest.mark.real_faces` path may use a cached CC0 frame and is skipped when that cache is absent.
- Benchmarks on LION are recorded when O1 measures layout against the §13 90 s budget.
