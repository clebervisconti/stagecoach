"""PDF print model (issue #49, SPEC §8.9). Chromium is mocked in unit tests."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.pdf_export import (
    SECTION_IDS,
    build_print_model,
    export_session_pdf,
    html_to_pdf,
    render_print_html,
)


def _report() -> dict:
    return {
        "session": {
            "id": "s1",
            "language": "en",
            "context_type": "keynote",
            "slot_min": 10,
        },
        "provenance": {
            "scoring_config_version": "1.0.0",
            "generated_at": "2026-10-14T00:00:00Z",
        },
        "media": {"duration_s": 540},
        "overall": {
            "score": 71,
            "display_band": 4,
            "level": 4,
            "coverage": 0.42,
            "confidence": 0.61,
        },
        "pillars": [{"id": "voice", "score": 74}, {"id": "visuals", "score": None}],
        "categories": [
            {
                "id": "fluency",
                "score": 48,
                "level": 3,
                "confidence_label": "high",
                "evidence_ids": ["ev-1"],
                "sources": ["S12"],
            },
            {
                "id": "visual_aids",
                "score": None,
                "applicable": False,
                "sources": ["S3"],
            },
        ],
        "metrics": [{"id": "pp_wpm", "raw_value": 145, "score": 95}],
        "evidence": [{"id": "ev-1", "t_start": 12.4, "text": "Filler sound at 00:12"}],
        "insights": {
            "summary": "Overall score 71",
            "opportunities": [
                {
                    "title": "Practice fluency",
                    "body": "fluency is at 48",
                    "fix": "Use the drill",
                    "drill_ids": ["pause-instead-of-um"],
                    "evidence_ids": ["ev-1"],
                }
            ],
            "strengths": [{"title": "pace pausing", "body": "scored 80"}],
        },
    }


def test_sections_match_spec() -> None:
    assert SECTION_IDS == (
        "cover",
        "opportunities",
        "strengths",
        "categories",
        "time",
        "metrics",
        "drills",
        "methodology",
    )


def test_html_omits_transcript_unless_requested() -> None:
    transcript = {"segments": [{"start": 0, "text": "Um hello secret words"}]}
    off = render_print_html(
        build_print_model(_report(), transcript=transcript, include_transcript=False)
    )
    on = render_print_html(
        build_print_model(_report(), transcript=transcript, include_transcript=True)
    )
    assert "secret words" not in off
    assert 'id="transcript"' not in off
    assert "secret words" in on
    assert 'id="transcript"' in on
    assert "<video" not in off.lower()


def test_html_has_svg_radar_and_na_not_zero() -> None:
    html = render_print_html(build_print_model(_report()))
    for section in SECTION_IDS:
        assert f'data-section="{section}"' in html
    assert "<svg" in html
    assert "N/A" in html
    assert "visual_aids" in html
    assert "1.0.0" in html
    assert "not emotion recognition" in html
    assert "71 ± 4" in html


def test_html_to_pdf_uses_playwright_chromium(tmp_path: Path) -> None:
    calls: dict[str, str] = {}

    class Page:
        def set_content(self, html, wait_until=None):
            calls["html"] = html

        def pdf(self, path, format, print_background):
            calls["format"] = format
            Path(path).write_bytes(b"%PDF-1.4 mock")

    class Browser:
        def new_page(self):
            return Page()

        def close(self):
            calls["closed"] = "1"

    class PW:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        class chromium:
            @staticmethod
            def launch(headless=True):
                calls["headless"] = str(headless)
                return Browser()

    import types
    import sys as sysmod

    fake = types.ModuleType("playwright")
    fake_sync = types.ModuleType("playwright.sync_api")
    fake_sync.sync_playwright = lambda: PW()
    sysmod.modules["playwright"] = fake
    sysmod.modules["playwright.sync_api"] = fake_sync

    dest = tmp_path / "report.pdf"
    html_to_pdf("<html><body>hi</body></html>", dest)
    assert dest.read_bytes().startswith(b"%PDF")
    assert calls["format"] == "A4"
    assert calls.get("closed") == "1"


def test_export_session_pdf_writes_html_and_pdf(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / "report.json").write_text(json.dumps(_report()), encoding="utf-8")
    (tmp_path / "transcript.json").write_text(
        json.dumps({"segments": [{"start": 0, "text": "keep out"}]}),
        encoding="utf-8",
    )

    def fake_pdf(html_text: str, dest: Path) -> Path:
        dest.write_bytes(b"%PDF-1.4 " + html_text.encode()[:80])
        return dest

    monkeypatch.setattr("pipeline.pdf_export.html_to_pdf", fake_pdf)
    result = export_session_pdf(
        tmp_path, tmp_path / "out.pdf", include_transcript=False
    )
    html = Path(result["html_path"]).read_text(encoding="utf-8")
    assert "keep out" not in html
    assert result["sections"] == list(SECTION_IDS)
    assert Path(result["path"]).is_file()
