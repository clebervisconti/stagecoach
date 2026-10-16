"""Trends series and config-major comparability (SPEC §4.6.3 / §8.8 / issue #64)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any


def major_version(version: str | None) -> str:
    parts = (version or "").split(".")
    return parts[0] if parts and parts[0] else ""


def session_comparable(
    row: dict[str, Any],
    *,
    context: str | None,
    language: str | None,
    config_major: str | None,
) -> tuple[bool, str | None]:
    reasons: list[str] = []
    if context and row.get("context_type") != context:
        reasons.append("different context")
    if language and row.get("language") != language:
        reasons.append("different language")
    row_major = major_version(str(row.get("config_version") or ""))
    if config_major and row_major != config_major:
        reasons.append("scoring-config major version differs")
    if reasons:
        return False, "; ".join(reasons)
    return True, None


def _pick_value(row: dict[str, Any], metric: str | None, category: str | None) -> float | None:
    if metric:
        metrics = row.get("metrics") or {}
        value = metrics.get(metric)
        return float(value) if value is not None else None
    if category:
        categories = row.get("categories") or {}
        value = categories.get(category)
        return float(value) if value is not None else None
    overall = row.get("overall")
    return float(overall) if overall is not None else None


def _callouts(comparable: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    numbered = [row for row in comparable if isinstance(row.get("value"), (int, float))]
    if len(numbered) < 2:
        return None, None
    first = numbered[-1]
    last = numbered[0]
    delta = float(last["value"]) - float(first["value"])
    improved = {
        "session_id": last["session_id"],
        "delta": delta,
        "from": first["value"],
        "to": last["value"],
    }
    # Needs attention: largest drop between consecutive comparable points (oldest → newest).
    worst: dict[str, Any] | None = None
    chronological = list(reversed(numbered))
    for prev, nxt in zip(chronological, chronological[1:]):
        drop = float(nxt["value"]) - float(prev["value"])
        if worst is None or drop < worst["delta"]:
            worst = {
                "session_id": nxt["session_id"],
                "delta": drop,
                "from": prev["value"],
                "to": nxt["value"],
            }
    return improved, worst


def build_trends(
    rows: Sequence[dict[str, Any]],
    *,
    metric: str | None = None,
    category: str | None = None,
    context: str | None = None,
    language: str | None = None,
) -> dict[str, Any]:
    """Build a trends payload. Newest row first. Incompatible rows stay listed."""
    ordered = list(rows)
    if not ordered:
        return {
            "filters": {
                "metric": metric,
                "category": category,
                "context": context,
                "language": language,
            },
            "series": [],
            "sparkline": [],
            "most_improved": None,
            "needs_attention": None,
            "comparable_count": 0,
        }
    ref = ordered[0]
    ref_context = context or str(ref.get("context_type") or "")
    ref_major = major_version(str(ref.get("config_version") or "1.0.0"))
    series: list[dict[str, Any]] = []
    comparable: list[dict[str, Any]] = []
    for row in ordered:
        ok, reason = session_comparable(
            row,
            context=ref_context or None,
            language=language,
            config_major=ref_major or None,
        )
        point = {
            "session_id": row.get("session_id"),
            "title": row.get("title"),
            "created_at": row.get("created_at"),
            "context_type": row.get("context_type"),
            "language": row.get("language"),
            "config_version": row.get("config_version"),
            "comparable": ok,
            "reason": None if ok else reason,
            "overall": row.get("overall"),
            "value": _pick_value(row, metric, category),
        }
        series.append(point)
        if ok:
            comparable.append(point)
    spark = [point["value"] if point["value"] is not None else point["overall"] for point in reversed(comparable)]
    improved, attention = _callouts(comparable)
    return {
        "filters": {
            "metric": metric,
            "category": category,
            "context": ref_context or context,
            "language": language,
        },
        "series": series,
        "sparkline": spark,
        "most_improved": improved,
        "needs_attention": attention,
        "comparable_count": len(comparable),
    }
