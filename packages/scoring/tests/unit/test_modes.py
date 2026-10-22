"""Delivery-mode weights, curve fallback, and stage parity (spec §10.2, §10.6)."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest
import yaml

from scoring import ScoringEngine, effective_weights
from scoring.engine import resolve_metric_curve

ROOT = Path(__file__).resolve().parents[4]
CONFIG_DIR = ROOT / "packages" / "scoring-config"
GOLDEN = ROOT / "services" / "analysis" / "tests" / "golden" / "fixtures"
CONTEXTS = [
    "keynote",
    "breakout",
    "exec_briefing",
    "sales_pitch",
    "virtual_meeting",
    "class_academic",
]
MODES = ["stage", "webinar", "online_talk", "recorded_video"]


def _load_yaml(version: str) -> dict:
    path = CONFIG_DIR / f"v{version}" / "scoring.yaml"
    with path.open() as handle:
        loaded = yaml.safe_load(handle)
    assert isinstance(loaded, dict)
    return loaded


def test_v110_validates_against_schema() -> None:
    schema = json.loads((CONFIG_DIR / "scoring-config.schema.json").read_text())
    jsonschema.validate(instance=_load_yaml("1.1.0"), schema=schema)


def test_effective_weights_sum_to_100_for_every_context_and_mode() -> None:
    config = _load_yaml("1.1.0")
    for context in CONTEXTS:
        for mode in MODES:
            weights = effective_weights(config, context, mode)
            total = sum(weights.values())
            assert total == pytest.approx(100.0, abs=1e-9), f"{context}×{mode}={total}"


def test_stage_effective_weights_match_v100() -> None:
    v100 = _load_yaml("1.0.0")
    v110 = _load_yaml("1.1.0")
    for context in CONTEXTS:
        expected = {key: float(value) for key, value in v100["weights"][context].items()}
        got = effective_weights(v110, context, "stage")
        for key, value in expected.items():
            assert got[key] == pytest.approx(value, abs=1e-9), f"{context}.{key}"


def test_missing_context_curve_returns_na_not_error() -> None:
    engine = ScoringEngine("1.0.0")
    # pp_wpm has context_curves for keynote/exec_briefing only.
    result = engine.score_metric(
        "pp_wpm",
        145.0,
        0.9,
        category_id="pace_pausing",
        context="virtual_meeting",
        mode="stage",
    )
    assert result["score"] is not None
    assert result["included"] is True

    bare = {
        "weight": 1.0,
        "unit": "ratio",
        "basis": {"kind": "heuristic", "source": "H"},
        "context_curves": {"keynote": [[0.0, 10.0], [1.0, 90.0]]},
    }
    curve = resolve_metric_curve(
        bare, context="breakout", mode="stage", metric_id="synthetic_missing"
    )
    assert curve == [[0.0, 10.0], [1.0, 90.0]]
    engine_v11 = ScoringEngine("1.1.0")
    engine_v11.config["categories"]["pace_pausing"]["metrics"]["synthetic_missing"] = bare
    scored = engine_v11.score_metric(
        "synthetic_missing",
        0.5,
        0.9,
        category_id="pace_pausing",
        context="breakout",
        mode="stage",
    )
    assert scored["score"] == pytest.approx(50.0)
    empty = {
        "weight": 1.0,
        "unit": "ratio",
        "basis": {"kind": "heuristic", "source": "H"},
        "context_curves": {"other_only": [[0.0, 0.0], [1.0, 100.0]]},
    }
    engine_v11.config["categories"]["pace_pausing"]["metrics"]["synthetic_empty"] = empty
    na = engine_v11.score_metric(
        "synthetic_empty",
        0.5,
        0.9,
        category_id="pace_pausing",
        context="breakout",
        mode="stage",
    )
    # Falls back to the first listed curve rather than raising.
    assert na["score"] is not None

    missing = {
        "weight": 1.0,
        "unit": "ratio",
        "basis": {"kind": "heuristic", "source": "H"},
        "context_curves": {},
    }
    engine_v11.config["categories"]["pace_pausing"]["metrics"]["synthetic_no_curve"] = missing
    blank = engine_v11.score_metric(
        "synthetic_no_curve",
        0.5,
        0.9,
        category_id="pace_pausing",
        context="breakout",
        mode="stage",
    )
    assert blank["score"] is None
    assert blank["included"] is False


def test_mode_restricted_metric_is_na_outside_listed_modes() -> None:
    engine = ScoringEngine("1.1.0")
    stage = engine.score_metric(
        "oe_open_visual_change_s",
        8.0,
        0.9,
        category_id="online_engagement",
        context="keynote",
        mode="stage",
    )
    recorded = engine.score_metric(
        "oe_open_visual_change_s",
        8.0,
        0.9,
        category_id="online_engagement",
        context="keynote",
        mode="recorded_video",
    )
    assert stage["score"] is None
    assert stage["included"] is False
    assert recorded["score"] is not None


@pytest.mark.parametrize("fixture_id", ["en_clean", "ptbr_clean", "noisy_low_snr"])
def test_stage_parity_against_v100_goldens(fixture_id: str) -> None:
    expected_path = GOLDEN / fixture_id / "expected" / "analysis_result.json"
    expected = json.loads(expected_path.read_text())
    v100 = ScoringEngine("1.0.0")
    v110 = ScoringEngine("1.1.0")
    context = expected["session"]["context_type"]

    by_category: dict[str, list[dict]] = {}
    for row in expected.get("metrics") or []:
        by_category.setdefault(row["category_id"], []).append(
            {
                "id": row["id"],
                "raw_value": row["raw_value"],
                "confidence": row["confidence"],
            }
        )

    want_cats = {row["id"]: row for row in expected.get("categories") or []}
    scored_v100: list[dict] = []
    scored_v110: list[dict] = []
    for category_id, want in want_cats.items():
        metrics = by_category.get(category_id, [])
        prepared_100 = []
        prepared_110 = []
        for item in metrics:
            one_100 = dict(item)
            one_100.update(
                v100.score_metric(
                    item["id"],
                    item["raw_value"],
                    float(item["confidence"] or 0),
                    category_id=category_id,
                    context=context,
                )
            )
            one_110 = dict(item)
            one_110.update(
                v110.score_metric(
                    item["id"],
                    item["raw_value"],
                    float(item["confidence"] or 0),
                    category_id=category_id,
                    context=context,
                    mode="stage",
                )
            )
            prepared_100.append(one_100)
            prepared_110.append(one_110)
        cat_100 = v100.score_category(category_id, prepared_100, context)
        cat_110 = v110.score_category(category_id, prepared_110, context, mode="stage")
        if want.get("applicable") is False:
            scored_v100.append(
                {
                    "id": category_id,
                    "score": None,
                    "confidence": 0.0,
                    "applicable": False,
                }
            )
            scored_v110.append(
                {
                    "id": category_id,
                    "score": None,
                    "confidence": 0.0,
                    "applicable": False,
                }
            )
            continue
        assert cat_110["score"] == cat_100["score"]
        if want.get("score") is not None and cat_100["score"] is not None:
            assert abs(float(cat_100["score"]) - float(want["score"])) <= 2.0
        scored_v100.append(
            {
                "id": category_id,
                "score": cat_100["score"],
                "confidence": cat_100["confidence"],
                "applicable": cat_100["applicable"],
            }
        )
        scored_v110.append(
            {
                "id": category_id,
                "score": cat_110["score"],
                "confidence": cat_110["confidence"],
                "applicable": cat_110["applicable"],
            }
        )

    overall_100 = v100.score_overall(scored_v100, context)
    overall_110 = v110.score_overall(scored_v110, context, mode="stage")
    assert overall_110["score"] == overall_100["score"]
    assert overall_110["partial"] == overall_100["partial"]
    expected_overall = (expected.get("overall") or {}).get("score")
    if expected_overall is None:
        assert overall_110["score"] is None
    else:
        assert overall_110["score"] is not None
        assert abs(float(overall_110["score"]) - float(expected_overall)) <= 2.0
