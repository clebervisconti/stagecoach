"""Golden fixtures: three licensed synthetic clips and noisy Low-confidence exclusion."""

from __future__ import annotations

import json

import jsonschema
import pytest

from tests.golden.audio import read_wav_meta
from tests.golden.build import GOLDEN_ROOT, PACKAGES, fixtures, run_fusion_for, write_all
from tests.golden.compare import compare_results

SCHEMA = json.loads((PACKAGES / "schemas" / "analysis_result.v1.json").read_text())


@pytest.fixture(scope="module", autouse=True)
def _golden_files() -> None:
    # Inputs and WAV only. Expected JSON is committed and must not be rewritten here.
    write_all(with_expected=False)


def test_three_fixtures_exist_with_documented_origin():
    specs = fixtures()
    assert {s["id"] for s in specs} == {"en_clean", "ptbr_clean", "noisy_low_snr"}
    languages = {s["language"] for s in specs}
    assert "en" in languages and "pt-BR" in languages
    for spec in specs:
        directory = GOLDEN_ROOT / spec["id"]
        manifest = json.loads((directory / "manifest.json").read_text())
        assert "personal" not in manifest["origin"].casefold() or "not a personal" in manifest["origin"].casefold()
        assert "CC0" in manifest["license"] or "generated" in manifest["license"].casefold()
        meta = read_wav_meta(directory / "audio.wav")
        assert meta["sample_rate"] == 16000
        assert meta["channels"] == 1
        assert meta["duration_s"] >= 0.5


@pytest.mark.parametrize("spec", fixtures(), ids=lambda s: s["id"])
def test_golden_comparison_tolerances(spec):
    actual = run_fusion_for(spec)
    expected = json.loads(
        (GOLDEN_ROOT / spec["id"] / "expected" / "analysis_result.json").read_text()
    )
    jsonschema.validate(instance=actual, schema=SCHEMA)
    errors = compare_results(actual, expected)
    assert errors == [], errors


def test_noisy_fixture_is_low_confidence_and_excluded_from_overall():
    spec = next(item for item in fixtures() if item["kind"] == "noisy")
    actual = run_fusion_for(spec)
    overall = actual["overall"]
    assert overall["score"] is None
    assert overall["confidence"] < 0.5
    assert actual["quality"]["snr_db"] == pytest.approx(10.0)
    assert actual["quality"]["warnings"]
    assert any("noise" in w.casefold() or "confidence" in w.casefold() for w in actual["quality"]["warnings"])
    for category in actual["categories"]:
        if category["id"] in {"pace_pausing", "vocal_variety", "fluency"}:
            assert (category.get("confidence") or 0) < 0.5
