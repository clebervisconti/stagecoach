#!/usr/bin/env python3
"""Load baked models with no outbound HTTP. Used by CI `docker run --network=none`."""

from __future__ import annotations

import os
import sys
from pathlib import Path

MODELS = Path(os.environ.get("MEDIAPIPE_MODELS_DIR", "/models"))


def _require(path: Path) -> Path:
    if not path.exists():
        raise SystemExit(f"missing baked file: {path}")
    return path


def main() -> int:
    _require(MODELS / "face_detection_yunet_2023mar.onnx")
    _require(MODELS / "silero-vad" / "hubconf.py")
    _require(MODELS / "pose_landmarker_full.task")
    _require(MODELS / "hand_landmarker.task")
    _require(MODELS / "face_landmarker.task")
    _require(MODELS / "faster-whisper" / "small" / "model.bin")
    _require(MODELS / "nltk_data" / "tokenizers" / "punkt_tab" / "english" / "abbrev_types.txt")

    os.environ.setdefault("NLTK_DATA", str(MODELS / "nltk_data"))
    os.environ.setdefault("FASTER_WHISPER_DIR", str(MODELS / "faster-whisper"))
    os.environ.setdefault("SILERO_VAD_DIR", str(MODELS / "silero-vad"))

    import nltk
    import whisperx
    from pipeline.layout.faces import YuNetFaceDetector
    from pipeline.stages.asr import resolve_whisper_model
    from pipeline.stages.alignment import load_silero_vad
    from pipeline.vision.models import ensure_models

    paths = ensure_models(MODELS)
    for name in (
        "pose_landmarker_full.task",
        "hand_landmarker.task",
        "face_landmarker.task",
    ):
        if name not in paths:
            raise SystemExit(f"ensure_models missed {name}")

    import numpy as np

    frame = np.zeros((160, 160, 3), dtype=np.uint8)
    YuNetFaceDetector(MODELS / "face_detection_yunet_2023mar.onnx").detect(frame)

    resolved = resolve_whisper_model("small")
    if not Path(resolved).is_dir():
        raise SystemExit(f"faster-whisper small was not resolved locally: {resolved}")

    from faster_whisper import WhisperModel

    WhisperModel(resolved, device="cpu", compute_type="int8", local_files_only=True)
    load_silero_vad()
    nltk.data.find("tokenizers/punkt_tab/english")
    assert callable(whisperx.load_align_model)
    print("offline_runtime_smoke ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
