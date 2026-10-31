"""E3-3: segment types from behaviour and a word count."""

from __future__ import annotations

import json
from pathlib import Path

from pipeline.screen.classify import classify_segment

MANIFEST = Path(__file__).parent / "fixtures" / "screen_flow_manifest.json"


def _rows(cls: str, count: int, ratio: float = 0.0):
    return [{"t": float(i), "cls": cls, "changed_ratio": ratio} for i in range(count)]


def test_segment_type_agreement():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    cases = [
        (classify_segment(_rows("static", 8), ocr_word_count=5), "SLIDE"),
        (classify_segment(_rows("pointer", 8), ocr_word_count=5), "SLIDE"),
        (classify_segment(_rows("scroll", 8, 0.2), ocr_word_count=0), "DEMO"),
        (classify_segment(_rows("motion", 8, 0.19), ocr_word_count=0), "VIDEO"),
        (classify_segment(_rows("static", 8), ocr_word_count=0), "IDLE"),
        (classify_segment(_rows("typing", 8, 0.02), ocr_word_count=1), "DEMO"),
        (classify_segment(_rows("static", 8), ocr_word_count=0, deck_page=2), "SLIDE"),
        (
            classify_segment(
                _rows("static", 5) + _rows("content_change", 3, 0.4),
                ocr_word_count=8,
            ),
            "DEMO",
        ),
    ]
    hits = sum(1 for got, expected in cases if got == expected)
    assert hits / len(cases) >= manifest["segment_agreement_min"], cases
