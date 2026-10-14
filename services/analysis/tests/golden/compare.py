"""Compare analysis_result documents with SPEC §11.6 tolerances."""

from __future__ import annotations

from typing import Any

SCORE_ABS = 2.0
METRIC_REL = 0.05


def _close(actual: float, expected: float, *, rel: float, abs_tol: float) -> bool:
    if expected == 0:
        return abs(actual - expected) <= abs_tol
    return abs(actual - expected) <= max(abs_tol, rel * abs(expected))


def compare_results(actual: dict[str, Any], expected: dict[str, Any]) -> list[str]:
    """Return human-readable mismatches. Empty list means the golden passed."""
    errors: list[str] = []

    def scores(path: str, got: Any, want: Any) -> None:
        if got is None and want is None:
            return
        if got is None or want is None:
            errors.append(f"{path}: expected {want!r}, got {got!r} (null must stay null)")
            return
        if not _close(float(got), float(want), rel=0.0, abs_tol=SCORE_ABS):
            errors.append(f"{path}: score {got} not within ±{SCORE_ABS:g} of {want}")

    scores("overall.score", (actual.get("overall") or {}).get("score"), (expected.get("overall") or {}).get("score"))

    want_label = (expected.get("overall") or {}).get("confidence_label")
    got_label = (actual.get("overall") or {}).get("confidence_label")
    if want_label and got_label != want_label:
        errors.append(f"overall.confidence_label: expected {want_label}, got {got_label}")

    want_cats = {c["id"]: c for c in expected.get("categories") or []}
    got_cats = {c["id"]: c for c in actual.get("categories") or []}
    for cat_id, want in want_cats.items():
        got = got_cats.get(cat_id)
        if got is None:
            errors.append(f"category {cat_id} missing")
            continue
        scores(f"categories.{cat_id}.score", got.get("score"), want.get("score"))
        if bool(got.get("applicable")) != bool(want.get("applicable")):
            errors.append(f"categories.{cat_id}.applicable: expected {want.get('applicable')}, got {got.get('applicable')}")

    want_metrics = {m["id"]: m for m in expected.get("metrics") or []}
    got_metrics = {m["id"]: m for m in actual.get("metrics") or []}
    for metric_id, want in want_metrics.items():
        got = got_metrics.get(metric_id)
        if got is None:
            errors.append(f"metric {metric_id} missing")
            continue
        wv, gv = want.get("raw_value"), got.get("raw_value")
        if wv is None and gv is None:
            continue
        if wv is None or gv is None:
            errors.append(f"metrics.{metric_id}.raw_value: expected {wv!r}, got {gv!r}")
            continue
        if not _close(float(gv), float(wv), rel=METRIC_REL, abs_tol=1e-6):
            errors.append(
                f"metrics.{metric_id}.raw_value: {gv} not within ±{METRIC_REL:.0%} of {wv}"
            )
    return errors
