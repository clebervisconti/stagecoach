"""MediaPipe Tasks model registry, download, and license notes (issue #38).

Licenses were re-checked on 2026-10-14. OpenFace is not listed and is not used.
"""

from __future__ import annotations

import hashlib
import os
import urllib.request
from pathlib import Path
from typing import Any

# Pinned float16/1 bundles from storage.googleapis.com/mediapipe-models.
# SHAs observed by sha256sum after download on 2026-10-14.

MODEL_REGISTRY: list[dict[str, Any]] = [
    {
        "component": "vision_pose",
        "model_name": "pose_landmarker_full",
        "version": "float16/1",
        "filename": "pose_landmarker_full.task",
        "url": "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/1/pose_landmarker_full.task",
        "sha256": "5134a3aad27a58b93da0088d431f366da362b44e3ccfbe3462b3827a839011b1",
        "license": "Apache-2.0",
        "license_evidence": (
            "Google maintainer schmidt-sebastian, mediapipe#6306 (2026-06-10): "
            "the pose_landmarker_full/float16/1 .task is released under Apache 2. "
            "Repo LICENSE Apache-2.0 fetched 2026-10-14 from github.com/google-ai-edge/mediapipe."
        ),
        "delegate": "CPU",
    },
    {
        "component": "vision_hands",
        "model_name": "hand_landmarker",
        "version": "float16/1",
        "filename": "hand_landmarker.task",
        "url": "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task",
        "sha256": "fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1",
        "license": "Apache-2.0",
        "license_evidence": (
            "schmidt-sebastian, mediapipe#6355 (2026-10-05): 'Our source and the models "
            "(unless otherwise noted) are licensed under Apache2.' Hand Landmarker page "
            "does not note a different license. Sample loader is Apache-2.0."
        ),
        "delegate": "CPU",
    },
    {
        "component": "vision_face",
        "model_name": "face_landmarker",
        "version": "float16/1",
        "filename": "face_landmarker.task",
        "url": "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task",
        "sha256": "64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff",
        "license": "Apache-2.0",
        "license_evidence": (
            "schmidt-sebastian, mediapipe#6355 (2026-10-05): models Apache2 unless noted. "
            "Face Landmarker model cards linked from the Tasks guide. Blendshape scores "
            "are stored as numbers only; no emotion classifier is used."
        ),
        "delegate": "CPU",
        "model_card": "https://storage.googleapis.com/mediapipe-assets/Model%20Card%20Blendshape%20V2.pdf",
    },
    {
        "component": "layout_face",
        "model_name": "face_detection_yunet_2023mar",
        "version": "2023mar",
        "filename": "face_detection_yunet_2023mar.onnx",
        "url": (
            "https://github.com/opencv/opencv_zoo/raw/main/models/"
            "face_detection_yunet/face_detection_yunet_2023mar.onnx"
        ),
        "sha256": "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4",
        "license": "MIT",
        "license_evidence": (
            "OpenCV Zoo face_detection_yunet LICENSE (MIT), fetched 22 Oct 2026: "
            "https://github.com/opencv/opencv_zoo/blob/main/models/face_detection_yunet/LICENSE "
            "(S66). Model is not vendored in this public repo. The worker image "
            "bakes it into /models at build time (ADR-075)."
        ),
        "delegate": "CPU",
        "used_by": "layout",
        "load_with": "layout",
    },
]


def default_models_dir() -> Path:
    env = os.environ.get("MEDIAPIPE_MODELS_DIR")
    if env:
        return Path(env)
    return Path.home() / ".cache" / "stagecoach" / "mediapipe-models"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_models(
    models_dir: Path | None = None,
    *,
    components: set[str] | None = None,
    include_layout: bool = False,
) -> dict[str, Path]:
    """Download missing models and verify SHA-256. Returns filename → path.

    Layout models (YuNet) are skipped unless `include_layout` is true or
    `components` names them. Vision callers must not pull YuNet by default.
    """
    root = Path(models_dir) if models_dir is not None else default_models_dir()
    root.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    for row in MODEL_REGISTRY:
        if components is not None and row["component"] not in components:
            continue
        if components is None and row.get("used_by") == "layout" and not include_layout:
            continue
        dest = root / row["filename"]
        if dest.exists() and _sha256(dest) == row["sha256"]:
            paths[row["filename"]] = dest
            continue
        tmp = dest.with_suffix(dest.suffix + ".part")
        urllib.request.urlretrieve(row["url"], tmp)
        digest = _sha256(tmp)
        if digest != row["sha256"]:
            tmp.unlink(missing_ok=True)
            raise RuntimeError(
                f"SHA-256 mismatch for {row['filename']}: got {digest}, expected {row['sha256']}"
            )
        tmp.replace(dest)
        paths[row["filename"]] = dest
    return paths
