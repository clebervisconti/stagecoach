"""YuNet must pin the OpenCV DNN backend/target so start-up does not warn."""

from __future__ import annotations

import inspect

import cv2
import numpy as np

from pipeline.layout.faces import YuNetFaceDetector


def test_yunet_create_uses_opencv_cpu_backend():
    source = inspect.getsource(YuNetFaceDetector._ensure)
    assert "DNN_BACKEND_OPENCV" in source
    assert "DNN_TARGET_CPU" in source
    assert "_opencv_quiet_yunet_dnn" in source
    assert cv2.dnn.DNN_BACKEND_OPENCV == 3
    assert cv2.dnn.DNN_TARGET_CPU == 0


def test_yunet_letterbox_pads_small_crop_without_stretching():
    from pipeline.layout.faces import YUNET_MIN_SIDE, letterbox_to_min_side

    frame = np.zeros((240, 320, 3), dtype=np.uint8)
    padded, origin_x, origin_y = letterbox_to_min_side(frame)
    assert padded.shape[0] >= YUNET_MIN_SIDE
    assert padded.shape[1] >= YUNET_MIN_SIDE
    assert padded.shape[0] == 240 + origin_y * 2 or padded.shape[0] == YUNET_MIN_SIDE
    assert origin_x == 0
    assert origin_y > 0
    # Original pixels are unchanged (not stretched).
    assert (padded[origin_y : origin_y + 240, origin_x : origin_x + 320] == 0).all()


def test_prepare_for_yunet_upscales_tiny_crop_only():
    from pipeline.layout.faces import YUNET_MIN_SIDE, prepare_for_yunet

    tiny = np.zeros((78, 106, 3), dtype=np.uint8)
    prepared, sx, sy, ox, oy = prepare_for_yunet(tiny)
    assert min(prepared.shape[:2]) >= YUNET_MIN_SIDE
    assert sx > 1.0 and sy > 1.0
    assert ox == 0 and oy == 0

    full = np.zeros((540, 960, 3), dtype=np.uint8)
    same, sx2, sy2, ox2, oy2 = prepare_for_yunet(full)
    assert same.shape == full.shape
    assert (sx2, sy2, ox2, oy2) == (1.0, 1.0, 0, 0)
