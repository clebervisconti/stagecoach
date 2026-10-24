"""Strength copy uses display names and does not repeat a top opportunity."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.stages.report import build_report

PACKAGES = Path(__file__).parents[3] / "packages"


def test_strength_skips_a_top_opportunity(tmp_path: Path):
    analysis = {
        "overall": {
            "score": 70,
            "display_band": 3,
            "coverage": 0.22,
            "partial": True,
            "confidence": 0.7,
            "level": 4,
        },
        "provenance": {"scoring_config_version": "1.1.0", "stages": []},
        "categories": [
            {"id": "visual_aids", "applicable": True, "score": 62, "level": 4, "confidence": 0.8},
            {"id": "pace_pausing", "applicable": True, "score": 80, "level": 4, "confidence": 0.8},
        ],
        "metrics": [],
        "evidence": [
            {
                "id": "ev-1",
                "category_id": "pace_pausing",
                "text": "Speaking rate 140.0 words per minute.",
                "t_start": 0,
                "t_end": 10,
            }
        ],
    }
    report = build_report(
        analysis=analysis,
        output_path=tmp_path / "report.json",
        packages_dir=PACKAGES,
        engine_opportunities=[{"category_id": "visual_aids", "target_score": 85, "impact": 12}],
    )
    strengths = report["insights"]["strengths"]
    assert [item["category_id"] for item in strengths] == ["pace_pausing"]
    assert strengths[0]["title"] == "Pace and pausing is a strength"
    assert "measured strength" not in strengths[0]["title"]
    assert report["insights"]["opportunities"][0]["title"] == "Practice visual aids"
    assert "visual_aids" not in report["insights"]["opportunities"][0]["title"]
