"""YuNet must pin the OpenCV DNN backend/target so start-up does not warn."""

from __future__ import annotations

import inspect

import cv2

from pipeline.layout.faces import YuNetFaceDetector


def test_yunet_create_uses_opencv_cpu_backend():
    source = inspect.getsource(YuNetFaceDetector._ensure)
    assert "DNN_BACKEND_OPENCV" in source
    assert "DNN_TARGET_CPU" in source
    assert cv2.dnn.DNN_BACKEND_OPENCV == 3
    assert cv2.dnn.DNN_TARGET_CPU == 0
