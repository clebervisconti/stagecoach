"""Tests for WhisperX alignment. Missing nltk/pandas must fail CI."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from pipeline.stages.alignment_gate import run_live_alignment
from pipeline.stages.asr import transcribe_audio

from .online.generate_online_fixtures import SPEECH_ASSET, synthesize_speech


def test_resolve_align_model_name_prefers_baked_pt(tmp_path: Path, monkeypatch):
    from pipeline.stages.alignment import resolve_align_model_name

    assert resolve_align_model_name("en") == "WAV2VEC2_ASR_BASE_960H"
    baked = tmp_path / "pt-model"
    baked.mkdir()
    (baked / "config.json").write_text("{}")
    (baked / "pytorch_model.bin").write_bytes(b"x")
    monkeypatch.setenv("ALIGNMENT_PT_DIR", str(baked))
    assert resolve_align_model_name("pt") == str(baked)
    monkeypatch.delenv("ALIGNMENT_PT_DIR")
    assert resolve_align_model_name("pt") == "jonatasgrosman/wav2vec2-large-xlsr-53-portuguese"


def test_whisperx_imports_nltk_and_pandas():
    """whisperX is installed --no-deps; these were missing on LION."""
    import nltk
    import pandas
    import whisperx
    from whisperx import alignment as whisperx_alignment

    assert whisperx_alignment.nltk is nltk
    assert callable(whisperx.load_align_model)
    assert callable(whisperx.align)
    _ = pandas.__version__


def test_alignment_on_synthetic_speech(tmp_path: Path):
    """Import whisperx and align a short espeak-ng clip. ASR words > 0."""
    speech = synthesize_speech(SPEECH_ASSET)
    assert speech.is_file()
    audio = tmp_path / "speech.wav"
    shutil.copy(speech, audio)

    asr = transcribe_audio(
        audio_path=audio,
        output_dir=tmp_path,
        session_id="align-speech",
        language="en",
        model_name="tiny",
    )
    assert asr.word_count > 0
    assert asr.segments

    transcript_path = tmp_path / "transcript.json"
    result = run_live_alignment(
        audio_path=audio,
        transcript_path=transcript_path,
        output_dir=tmp_path,
        session_id="align-speech",
        language="en",
    )
    assert result["status"] == "succeeded", result
    assert int((result.get("metrics") or {}).get("aligned_words") or 0) > 0
    payload = json.loads((tmp_path / "align-speech_alignment.json").read_text())
    assert payload["aligned_words"]
    assert payload["mean_alignment_score"] >= 0
