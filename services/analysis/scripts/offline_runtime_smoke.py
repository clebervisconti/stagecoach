#!/usr/bin/env python3
"""Load baked models with no outbound HTTP. Used by CI `docker run --network=none`."""

from __future__ import annotations

import os
import sys
from pathlib import Path

MODELS = Path(os.environ.get("MEDIAPIPE_MODELS_DIR", "/models"))
SPEECH = (
    Path(__file__).resolve().parents[1]
    / "tests"
    / "online"
    / "fixtures"
    / "assets"
    / "synthetic_speech.wav"
)


def _require(path: Path) -> Path:
    if not path.exists():
        raise SystemExit(f"missing baked file: {path}")
    return path


def _align(language: str, model_name: str, audio_path: Path, text: str) -> None:
    import whisperx

    model, metadata = whisperx.load_align_model(
        language_code=language,
        device="cpu",
        model_name=model_name,
        model_cache_only=True,
    )
    audio = whisperx.load_audio(str(audio_path))
    duration = min(3.0, float(audio.shape[0]) / 16000.0)
    result = whisperx.align(
        [{"start": 0.0, "end": duration, "text": text}],
        model,
        metadata,
        audio,
        "cpu",
        return_char_alignments=False,
    )
    del model
    if not isinstance(result, dict) or "segments" not in result:
        raise SystemExit(f"{language} alignment returned no segments")


def main() -> int:
    _require(MODELS / "face_detection_yunet_2023mar.onnx")
    _require(MODELS / "silero-vad" / "hubconf.py")
    _require(MODELS / "pose_landmarker_full.task")
    _require(MODELS / "hand_landmarker.task")
    _require(MODELS / "face_landmarker.task")
    _require(MODELS / "faster-whisper" / "small" / "model.bin")
    _require(MODELS / "nltk_data" / "tokenizers" / "punkt_tab" / "english" / "abbrev_types.txt")
    _require(
        MODELS
        / "torch"
        / "hub"
        / "checkpoints"
        / "wav2vec2_fairseq_base_ls960_asr_ls960.pth"
    )
    _require(MODELS / "alignment" / "wav2vec2-large-xlsr-53-portuguese" / "pytorch_model.bin")
    _require(MODELS / "alignment" / "wav2vec2-large-xlsr-53-portuguese" / "config.json")
    _require(SPEECH)

    os.environ.setdefault("NLTK_DATA", str(MODELS / "nltk_data"))
    os.environ.setdefault("FASTER_WHISPER_DIR", str(MODELS / "faster-whisper"))
    os.environ.setdefault("SILERO_VAD_DIR", str(MODELS / "silero-vad"))
    os.environ.setdefault("TORCH_HOME", str(MODELS / "torch"))
    os.environ.setdefault(
        "ALIGNMENT_PT_DIR",
        str(MODELS / "alignment" / "wav2vec2-large-xlsr-53-portuguese"),
    )
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"

    import nltk
    import whisperx
    from pipeline.layout.faces import YuNetFaceDetector
    from pipeline.stages.alignment import resolve_align_model_name
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

    en_name = resolve_align_model_name("en")
    pt_name = resolve_align_model_name("pt")
    if en_name != "WAV2VEC2_ASR_BASE_960H":
        raise SystemExit(f"en align model should stay the torchaudio bundle, got {en_name}")
    if not Path(pt_name).is_dir():
        raise SystemExit(f"pt align model was not resolved to a baked directory: {pt_name}")

    _align("en", en_name, SPEECH, "Welcome to this webinar.")
    _align("pt", pt_name, SPEECH, "Bem vindo a este webinar.")
    print("offline_runtime_smoke ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
