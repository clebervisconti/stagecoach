"""Personal baseline median/MAD and z badge (issue #66)."""

from scoring.baseline import (
    MIN_SESSIONS,
    baseline_for_metric,
    build_snapshot,
    keep_population_score,
    mean_absolute_deviation,
    snapshot_to_dict,
    z_badge,
)


def test_requires_three_same_language_sessions():
    assert baseline_for_metric("pp_wpm", [120.0, 130.0], "en") is None
    row = baseline_for_metric("pp_wpm", [120.0, 130.0, 140.0], "en")
    assert row is not None
    assert row.n == 3
    assert row.median == 130.0
    assert row.language == "en"


def test_mad_and_z_formula():
    values = [10.0, 20.0, 30.0]
    assert mean_absolute_deviation(values) == 10.0
    row = baseline_for_metric("pp_wpm", values, "en")
    assert row is not None
    z = z_badge(40.0, row)
    assert z is not None
    assert abs(z - (20.0 / (1.4826 * 10.0))) < 1e-9


def test_zero_mad_is_na_badge():
    row = baseline_for_metric("pp_wpm", [130.0, 130.0, 130.0], "pt-BR")
    assert row is not None
    assert row.mad == 0.0
    assert z_badge(130.0, row) is None


def test_snapshot_storage_and_population_score_unchanged():
    snap = build_snapshot(
        {"pp_wpm": [120.0, 130.0, 140.0], "fl_filler_sounds_per_min": [1.0]},
        "en",
        n_sessions=3,
    )
    assert snap is not None
    assert snap.n_sessions >= MIN_SESSIONS
    assert "pp_wpm" in snap.metrics
    assert "fl_filler_sounds_per_min" not in snap.metrics
    blob = snapshot_to_dict(snap)
    assert blob["language"] == "en"
    assert blob["metrics"]["pp_wpm"]["median"] == 130.0
    assert keep_population_score(72.0, 1.5) == 72.0


def test_snapshot_none_before_three_sessions():
    assert build_snapshot({"pp_wpm": [120.0, 130.0]}, "en", n_sessions=2) is None
