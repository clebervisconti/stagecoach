"""Tests for the deterministic private-beta report."""

import json
import sys
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.stages.mvp_report import build_mvp_report


def _inputs(tmp_path: Path, language: str = "en") -> dict:
    transcript = {
        "language": language,
        "duration": 10,
        "mean_word_probability": 0.9,
        "segments": [
            {
                "id": 0,
                "start": 0.0,
                "end": 10.0,
                "text": "Um clear words for this test.",
                "words": [
                    {"word": "Um", "start": 0.0, "end": 0.2, "probability": 0.92},
                    {"word": "clear", "start": 0.3, "end": 0.7, "probability": 0.95},
                    {"word": "words", "start": 0.8, "end": 1.2, "probability": 0.94},
                ],
            }
        ],
    }
    transcript_path = tmp_path / "transcript.json"
    transcript_path.write_text(json.dumps(transcript))
    audio_path = tmp_path / "audio_metrics.json"
    audio_path.write_text(
        json.dumps(
            {
                "pvq_median": 0.18,
                "snr_db": 22.0,
                "noise_flag": False,
                "music_flag": False,
                "pause_counts": {"boundary": 2},
                "confidence": {"inclusion_cap": 1.0},
            }
        )
    )
    prosody_path = tmp_path / "prosody.parquet"
    pq.write_table(
        pa.table(
            {
                "time_s": [0.01, 0.5, 1.0],
                "f0_st": [0.0, 1.0, -1.0],
                "intensity_db": [0.0, 2.0, -2.0],
            }
        ),
        prosody_path,
    )
    return {
        "transcript_path": transcript_path,
        "audio_metrics_path": audio_path,
        "prosody_path": prosody_path,
    }


def test_report_is_partial_and_evidence_seeks_to_filler(tmp_path: Path):
    files = _inputs(tmp_path)
    output = tmp_path / "report.json"
    report = build_mvp_report(
        session_id="00000000-0000-4000-8000-000000000001",
        context_type="keynote",
        language="en",
        slot_min=1,
        ingest={"media_info": {"duration": 10}},
        packages_dir=Path(__file__).parents[3] / "packages",
        output_path=output,
        **files,
    )
    assert report["partial"] is True
    assert report["overall"] is not None
    assert report["evidence"][0]["t_start"] == 0.0
    assert report["evidence"][0]["text"] == "Filler sound: “Um”"
    assert output.exists()
    assert "facial_affect" in report["unavailable_categories"]


def test_portuguese_short_e_is_not_counted_as_filler(tmp_path: Path):
    files = _inputs(tmp_path, "pt")
    transcript = json.loads(files["transcript_path"].read_text())
    transcript["segments"][0]["words"][0]["word"] = "é"
    files["transcript_path"].write_text(json.dumps(transcript))
    report = build_mvp_report(
        session_id="00000000-0000-4000-8000-000000000002",
        context_type="class_academic",
        language="pt-BR",
        slot_min=None,
        ingest={"media_info": {"duration": 10}},
        packages_dir=Path(__file__).parents[3] / "packages",
        output_path=tmp_path / "report.json",
        **files,
    )
    filler_metric = next(
        metric for metric in report["metrics"] if metric["id"] == "fl_filler_sounds_per_min"
    )
    assert filler_metric["value"] == 0
    assert report["evidence"] == []
