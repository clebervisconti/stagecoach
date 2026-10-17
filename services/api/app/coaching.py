"""Report objectives, planned-vs-actual rows, and personal-baseline badges.

Scores stay on the population curve. The badge is a z against the speaker's
own median after three same-language sessions.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional


def _scoring_path() -> None:
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        candidate = parent / "packages" / "scoring"
        if candidate.exists() and str(candidate) not in sys.path:
            sys.path.insert(0, str(candidate))
            return
    mounted = Path("/packages/scoring")
    if mounted.exists() and str(mounted) not in sys.path:
        sys.path.insert(0, str(mounted))


def planned_rows(outline: list[Any] | None) -> list[dict[str, Any]]:
    """Planned section times. Actuals stay null until a rehearsal is timed."""
    rows: list[dict[str, Any]] = []
    for item in outline or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("section") or item.get("name") or "")
        if not name:
            continue
        minutes = item.get("minutes")
        rows.append(
            {
                "section": name,
                "planned_min": minutes,
                "actual_min": None,
                "delta_min": None,
                "note": "Actual section time stays N/A until this rehearsal is timed against the plan.",
            }
        )
    return rows


def coaching_document(
    *,
    objectives: list[Any] | None,
    outline: list[Any] | None,
    rehearsal_groups: list[list[dict[str, Any]]],
    language: str,
    history: dict[str, list[float]],
    n_sessions: int,
    current_metrics: list[dict[str, Any]],
    linked_plan: bool,
) -> dict[str, Any]:
    _scoring_path()
    from scoring.baseline import (
        build_snapshot,
        keep_population_score,
        snapshot_to_dict,
        z_badge,
    )
    from scoring.section_variance import rehearsal_progress

    if not linked_plan:
        progress: dict[str, Any] = {
            "ready": False,
            "reason": "This session is not linked to a talk plan.",
            "objectives": [],
        }
    else:
        progress = rehearsal_progress(rehearsal_groups)

    snapshot = build_snapshot(history, language, n_sessions)
    badges: list[dict[str, Any]] = []
    stored = None
    if snapshot is not None:
        stored = snapshot_to_dict(snapshot)
        for metric in current_metrics:
            metric_id = str(metric.get("metric_id") or "")
            raw = metric.get("raw_value")
            base = snapshot.metrics.get(metric_id)
            if base is None or raw is None:
                continue
            z = z_badge(float(raw), base)
            population = metric.get("score")
            kept = (
                keep_population_score(float(population), z)
                if isinstance(population, (int, float))
                else None
            )
            badges.append(
                {
                    "metric_id": metric_id,
                    "z": z,
                    "median": base.median,
                    "mad": base.mad,
                    "n": base.n,
                    "population_score": population,
                    "kept_score": kept,
                }
            )
    baseline = (
        {"ready": True, **stored}
        if stored
        else {
            "ready": False,
            "language": language,
            "n_sessions": n_sessions,
            "reason": "Baseline appears after 3 sessions in this language.",
            "metrics": {},
        }
    )
    return {
        "objectives": list(objectives or []),
        "planned_vs_actual": planned_rows(outline),
        "rehearsal_progress": progress,
        "baseline": baseline,
        "badges": badges,
    }


def remember_baseline(user: Any, language: str, baseline: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Store a ready snapshot on the user. Returns the JSON to persist, or None."""
    if not baseline.get("ready"):
        return None
    current = dict(getattr(user, "personal_baselines", None) or {})
    current[language] = {
        "language": baseline.get("language"),
        "n_sessions": baseline.get("n_sessions"),
        "metrics": baseline.get("metrics") or {},
    }
    user.personal_baselines = current
    return current
