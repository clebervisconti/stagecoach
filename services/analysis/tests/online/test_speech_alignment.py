"""Online fixtures must carry speech so ASR and alignment actually run."""

from __future__ import annotations

import json
from pathlib import Path

from pipeline.stages.alignment_gate import run_live_alignment
from pipeline.stages.asr import transcribe_audio

from .generate_online_fixtures import generate_one


def test_composite_fixture_asr_words_and_alignment(tmp_path: Path):
    video = generate_one("composite_pip_tr", tmp_path, duration=4.0, width=640, height=360)
    audio = tmp_path / "audio16k.wav"
    import subprocess

    subprocess.run(
        [
            "ffmpeg",
            "-i",
            str(video),
            "-ar",
            "16000",
            "-ac",
            "1",
            "-y",
            str(audio),
        ],
        check=True,
        capture_output=True,
    )
    assert audio.is_file()

    asr = transcribe_audio(
        audio_path=audio,
        output_dir=tmp_path,
        session_id="fixture-speech",
        language="en",
        model_name="tiny",
    )
    assert asr.word_count > 0, "fixture audio must be speech, not silence"

    result = run_live_alignment(
        audio_path=audio,
        transcript_path=tmp_path / "transcript.json",
        output_dir=tmp_path,
        session_id="fixture-speech",
        language="en",
    )
    assert result["status"] == "succeeded", result
    assert int((result.get("metrics") or {}).get("aligned_words") or 0) > 0
    payload = json.loads((tmp_path / "fixture-speech_alignment.json").read_text())
    assert payload["aligned_words"]
