"""Layout save validation, optimistic lock, and F6 media reference."""

import os

os.environ.setdefault("DATABASE_URL", "postgresql://stagecoach@127.0.0.1/stagecoach_test")

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.layout_schema import (
    LayoutPutBody,
    confirmed_document,
    count_edits,
    reanalyse_seed,
    validate_timeline,
    validate_window_inside,
    windows_equal,
)
from app.rate_limit import MemoryStore
from app.routers.layout import layout_write_allowed, reference_job_media
from app.routers.sessions import AnalysisWindow


def _segment(start: float, end: float, regions: list | None = None, index: int = 0):
    return {
        "index": index,
        "t_start": start,
        "t_end": end,
        "kind": "composite",
        "confidence": 0.9,
        "regions": regions
        or [
            {
                "id": "r0",
                "role": "camera",
                "x": 0.7,
                "y": 0.0,
                "w": 0.3,
                "h": 0.3,
                "source": "auto",
            }
        ],
    }


def _body(**overrides) -> LayoutPutBody:
    payload = {
        "version": 1,
        "segments": [_segment(0, 120)],
        "analysis_window": None,
    }
    payload.update(overrides)
    return LayoutPutBody(**payload)


def test_trim_under_60_seconds_is_rejected():
    with pytest.raises(ValidationError):
        AnalysisWindow(start_s=0, end_s=59.9)
    window = AnalysisWindow(start_s=10, end_s=70)
    assert window.end_s - window.start_s == 60


def test_region_must_cover_five_percent_and_stay_inside():
    with pytest.raises(ValidationError):
        _body(segments=[_segment(0, 120, [{"id": "r0", "role": "camera", "x": 0, "y": 0, "w": 0.04, "h": 0.2}])])
    with pytest.raises(ValidationError):
        _body(segments=[_segment(0, 120, [{"id": "r0", "role": "camera", "x": 0.9, "y": 0, "w": 0.2, "h": 0.2}])])
    with pytest.raises(ValidationError):
        _body(
            segments=[
                _segment(
                    0,
                    120,
                    [
                        {"id": "a", "role": "camera", "x": 0, "y": 0, "w": 0.2, "h": 0.2},
                        {"id": "b", "role": "camera", "x": 0.5, "y": 0, "w": 0.2, "h": 0.2},
                    ],
                )
            ]
        )


def test_segments_must_cover_without_overlap():
    body = _body(segments=[_segment(0, 40, index=0), _segment(40, 120, index=1)])
    validate_timeline(body.segments, 120)
    gapped = _body(segments=[_segment(0, 40, index=0), _segment(50, 120, index=1)])
    with pytest.raises(ValueError, match="contiguous"):
        validate_timeline(gapped.segments, 120)
    overlap = _body(segments=[_segment(0, 70, index=0), _segment(60, 120, index=1)])
    with pytest.raises(ValueError, match="overlap"):
        validate_timeline(overlap.segments, 120)


def test_window_must_sit_inside_the_recording():
    window = AnalysisWindow(start_s=0, end_s=90)
    validate_window_inside(window, 120)
    with pytest.raises(ValueError, match="inside"):
        validate_window_inside(AnalysisWindow(start_s=80, end_s=150), 120)


def test_edit_count_tracks_role_geometry_and_window():
    detected = {"segments": [_segment(0, 120)], "analysis_window": None}
    assert count_edits(detected, _body()) == 0
    moved = _segment(0, 120, [{"id": "r0", "role": "screen", "x": 0.1, "y": 0.1, "w": 0.4, "h": 0.4, "source": "user"}])
    assert count_edits(detected, _body(segments=[moved])) >= 1
    assert count_edits(detected, _body(analysis_window={"start_s": 0, "end_s": 90})) >= 1
    assert windows_equal(None, None)
    assert windows_equal({"start_s": 0, "end_s": 90}, {"start_s": 0.01, "end_s": 90.02})


def test_confirmed_document_bumps_version_and_restarts_on_reanalyse():
    detected = {"detector_version": "1.0.0", "confidence": 0.8, "segments": [_segment(0, 120)], "frame": {"duration_s": 120}}
    body = _body(segments=[_segment(0, 120)])
    document = confirmed_document(detected, body, version=2, status="confirmed")
    assert document["version"] == 2
    assert document["status"] == "confirmed"
    seed = reanalyse_seed(document)
    assert seed["version"] == 1
    assert seed["status"] == "detected"
    assert seed["segments"][0]["regions"][0]["role"] == "camera"


def test_layout_write_bucket_denies_after_burst():
    store = MemoryStore()
    allowed = [layout_write_allowed(store, "user-1", now=1_000)[0] for _ in range(8)]
    assert all(allowed)
    assert layout_write_allowed(store, "user-1", now=1_000)[0] is False


def test_reference_job_media_keeps_transcript_on_the_old_job(tmp_path: Path):
    src = tmp_path / "old"
    src.mkdir()
    (src / "ingest.json").write_text('{"artifacts": {"audio16k": "/keep/audio.wav"}}\n')
    (src / "layout.json").write_text("{}\n")
    (src / "transcript.json").write_text('{"language": "en"}\n')
    (src / "asr_input.json").write_text("{}\n")
    preview = src / "layout_preview"
    preview.mkdir()
    (preview / "segment_000.jpg").write_bytes(b"jpeg")
    dest = tmp_path / "new"
    reference_job_media(src, dest)
    assert json.loads((dest / "ingest.json").read_text())["artifacts"]["audio16k"].endswith("audio.wav")
    assert not (dest / "transcript.json").exists()
    assert not (dest / "asr_input.json").exists()
    assert (dest / "layout_preview").is_symlink()
    assert (dest / "layout_preview" / "segment_000.jpg").read_bytes() == b"jpeg"


def test_put_layout_conflict_keeps_the_row(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from app.routers import layout as layout_router

    row = SimpleNamespace(
        version=3,
        detected={"frame": {"duration_s": 120, "width": 100, "height": 100}, "segments": [_segment(0, 120)]},
        confirmed=None,
        status="detected",
        confidence=0.8,
        edit_count=0,
        detector_version="1.0.0",
    )

    class DB:
        def query(self, _model):
            return self

        def filter(self, *_args):
            return self

        def order_by(self, *_args):
            return self

        def first(self):
            return row

        def commit(self):
            raise AssertionError("conflict must not commit")

        def add(self, _obj):
            raise AssertionError("conflict must not insert")

    monkeypatch.setattr(layout_router, "_owned_session", lambda *_a, **_k: SimpleNamespace(id="sess", status="layout_review"))
    monkeypatch.setattr(layout_router, "_latest_job", lambda *_a, **_k: SimpleNamespace(id="job"))
    monkeypatch.setattr(layout_router, "_enforce_layout_write", lambda *_a, **_k: None)
    monkeypatch.setattr(layout_router, "MEDIA_ROOT", tmp_path)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(layout_router.put_layout("sess", _body(version=1), SimpleNamespace(id="user"), DB()))
    assert exc.value.status_code == 409
    assert row.version == 3
    assert row.confirmed is None


def test_put_layout_saves_corrected_boxes_and_enqueues(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from app.routers import layout as layout_router

    row = SimpleNamespace(
        version=1,
        detected={
            "detector_version": "1.0.0",
            "confidence": 0.86,
            "frame": {"duration_s": 120, "width": 1920, "height": 1080},
            "segments": [_segment(0, 120)],
            "analysis_window": None,
        },
        confirmed=None,
        status="detected",
        confidence=0.86,
        edit_count=0,
        detector_version="1.0.0",
    )
    session = SimpleNamespace(id="sess", status="layout_review", analysis_window=None)
    job = SimpleNamespace(id="job")
    enqueued: dict = {}

    class DB:
        def query(self, _model):
            return self

        def filter(self, *_args):
            return self

        def order_by(self, *_args):
            return self

        def first(self):
            return row

        def commit(self):
            return None

        def add(self, _obj):
            return None

    def capture_enqueue(*_args, **kwargs):
        enqueued.update(kwargs)

    monkeypatch.setattr(layout_router, "_owned_session", lambda *_a, **_k: session)
    monkeypatch.setattr(layout_router, "_latest_job", lambda *_a, **_k: job)
    monkeypatch.setattr(layout_router, "_enforce_layout_write", lambda *_a, **_k: None)
    monkeypatch.setattr(layout_router, "_enqueue_analysis", capture_enqueue)
    monkeypatch.setattr(layout_router, "MEDIA_ROOT", tmp_path)
    moved = _segment(
        0,
        120,
        [{"id": "r0", "role": "camera", "x": 0.6, "y": 0.0, "w": 0.3, "h": 0.3, "source": "user"}],
    )
    body = _body(segments=[moved], analysis_window={"start_s": 0, "end_s": 90})
    result = asyncio.run(layout_router.put_layout("sess", body, SimpleNamespace(id="user"), DB()))
    assert result["status"] == "processing"
    assert result["layout_version"] == 2
    assert result["edit_count"] >= 1
    assert row.status == "corrected"
    assert session.status == "processing"
    assert session.analysis_window["end_s"] == 90
    saved = json.loads((tmp_path / "sess" / "job" / "layout.json").read_text())
    assert saved["segments"][0]["regions"][0]["x"] == 0.6
    assert saved["segments"][0]["regions"][0]["role"] == "camera"
    assert enqueued["analysis_window"]["end_s"] == 90
    assert enqueued["audio_only"] is False
    assert enqueued["layout_path"].endswith("layout.json")
