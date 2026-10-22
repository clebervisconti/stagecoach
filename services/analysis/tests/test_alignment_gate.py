"""The live job skips alignment when WhisperX cannot be imported."""

import sys
from pathlib import Path

from pipeline.stages.alignment_gate import run_live_alignment


def test_alignment_skips_when_the_stage_cannot_be_imported(monkeypatch, tmp_path: Path):
    monkeypatch.setitem(sys.modules, "pipeline.stages.alignment", None)
    result = run_live_alignment(
        audio_path=tmp_path / "audio.wav",
        transcript_path=tmp_path / "transcript.json",
        output_dir=tmp_path,
        session_id="session-1",
        language="en",
    )
    assert result["status"] == "skipped"
    assert result["metrics"]["reason"] == "alignment_unavailable"


def test_alignment_reports_success_from_the_stage(monkeypatch, tmp_path: Path):
    class _Result:
        def to_dict(self):
            return {
                "aligned_words": [{"word": "hello"}],
                "mean_alignment_score": 0.8,
                "gap_fills_count": 1,
            }

    class _Module:
        @staticmethod
        def align_transcript(**kwargs):
            assert kwargs["session_id"] == "session-1"
            return _Result()

    monkeypatch.setitem(sys.modules, "pipeline.stages.alignment", _Module())
    result = run_live_alignment(
        audio_path=tmp_path / "audio.wav",
        transcript_path=tmp_path / "transcript.json",
        output_dir=tmp_path,
        session_id="session-1",
        language="en",
    )
    assert result["status"] == "succeeded"
    assert result["metrics"]["aligned_words"] == 1
    assert result["metrics"]["mean_alignment_score"] == 0.8
