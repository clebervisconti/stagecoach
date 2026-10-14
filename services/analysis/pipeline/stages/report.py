"""Report stage (issue #30, SPEC §6.8, §8.10).

Phrases strengths, fixes, and a summary from computed facts only.
Every number in prose must already exist in the facts payload.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Optional

import yaml

from .fusion_scoring import STAGE_VERSION, _packages_dir

logger = logging.getLogger(__name__)

FORBIDDEN = re.compile(
    r"\b(happy|sad|angry|anxious|fearful|excited|confident|emotion|feels|feeling)\b",
    re.IGNORECASE,
)
NUMBER = re.compile(r"-?\d+(?:\.\d+)?")


def _load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text()) if path.exists() else {}


def _facts_payload(analysis: dict[str, Any]) -> dict[str, Any]:
    return {
        "overall": analysis.get("overall"),
        "categories": [
            {
                "id": c["id"],
                "score": c.get("score"),
                "level": c.get("level"),
                "confidence": c.get("confidence"),
                "applicable": c.get("applicable"),
                "na_reason": c.get("na_reason"),
            }
            for c in analysis.get("categories", [])
        ],
        "metrics": [
            {"id": m["id"], "raw_value": m.get("raw_value"), "score": m.get("score")}
            for m in analysis.get("metrics", [])
        ],
        "coverage": (analysis.get("overall") or {}).get("coverage"),
        "partial": (analysis.get("overall") or {}).get("partial"),
        "unavailable_count": sum(1 for c in analysis.get("categories", []) if not c.get("applicable")),
        "scored_count": sum(1 for c in analysis.get("categories", []) if c.get("applicable") and c.get("score") is not None),
        "evidence_count": len(analysis.get("evidence") or []),
        "scoring_config_version": (analysis.get("provenance") or {}).get("scoring_config_version"),
    }


def _numbers_in(obj: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(obj, dict):
        for value in obj.values():
            found |= _numbers_in(value)
    elif isinstance(obj, list):
        for value in obj:
            found |= _numbers_in(value)
    elif isinstance(obj, bool):
        return found
    elif isinstance(obj, (int, float)):
        found.add(str(int(obj)) if float(obj).is_integer() else f"{obj:.2f}".rstrip("0").rstrip("."))
        found.add(str(obj))
        if isinstance(obj, float):
            found.add(f"{obj:.1f}")
            found.add(f"{obj:.2f}")
    elif isinstance(obj, str):
        found.update(NUMBER.findall(obj))
    return found


def _assert_numbers_from_facts(text: str, facts: dict[str, Any]) -> None:
    allowed = _numbers_in(facts)
    for token in NUMBER.findall(text):
        if token not in allowed:
            raise ValueError(f"Number {token} in report prose is not in the facts payload")


def _assert_no_emotion(text: str) -> None:
    match = FORBIDDEN.search(text)
    if match:
        raise ValueError(f"Emotion term {match.group(0)!r} is not allowed in report text")


def _match_drills(metrics: list[dict[str, Any]], packages_dir: Path) -> dict[str, list[str]]:
    rules = _load_yaml(packages_dir / "scoring-config" / "v1.0.0" / "drill_rules.yaml")
    by_metric: dict[str, list[str]] = {}
    values = {m["id"]: m.get("raw_value") for m in metrics}
    for rule in rules.get("rules", []):
        cond = rule.get("when") or {}
        metric_id = cond.get("metric")
        raw = values.get(metric_id)
        if raw is None:
            continue
        op = cond.get("op")
        expected = cond.get("value")
        hit = False
        if op == ">" and isinstance(raw, (int, float)) and isinstance(expected, (int, float)):
            hit = raw > expected
        elif op == "<" and isinstance(raw, (int, float)) and isinstance(expected, (int, float)):
            hit = raw < expected
        elif op == "==":
            hit = raw == expected
        if hit:
            by_metric.setdefault(metric_id, [])
            for drill in rule.get("drills") or []:
                if drill not in by_metric[metric_id]:
                    by_metric[metric_id].append(drill)
    return by_metric


def _insight(
    *,
    category_id: str,
    title: str,
    body: str,
    fix: Optional[str],
    drill_ids: list[str],
    evidence_ids: list[str],
    impact: Optional[float],
) -> dict[str, Any]:
    if not evidence_ids:
        raise ValueError("insight requires at least one evidence id")
    return {
        "category_id": category_id,
        "title": title[:120],
        "body": body[:800],
        "fix": None if fix is None else fix[:600],
        "drill_ids": drill_ids,
        "evidence_ids": evidence_ids,
        "impact_estimate": impact,
    }


def _label(category_id: str) -> str:
    return category_id.replace("_", " ")


def build_report(
    *,
    analysis: dict[str, Any],
    output_path: Path,
    packages_dir: Optional[Path] = None,
    engine_opportunities: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    """Fill insights from facts, attach drills, write report.json."""
    packages = packages_dir or _packages_dir()
    facts = _facts_payload(analysis)
    drills = _match_drills(analysis.get("metrics") or [], packages)
    evidence = analysis.get("evidence") or []
    by_cat = {c["id"]: c for c in analysis.get("categories") or []}
    evidence_by_cat: dict[str, list[str]] = {}
    for item in evidence:
        evidence_by_cat.setdefault(item["category_id"], []).append(item["id"])
    fallback_evidence = [item["id"] for item in evidence[:1]]

    strengths: list[dict[str, Any]] = []
    weaknesses: list[dict[str, Any]] = []
    for category in analysis.get("categories") or []:
        if not category.get("applicable") or category.get("score") is None:
            continue
        eids = evidence_by_cat.get(category["id"]) or fallback_evidence
        if not eids:
            continue
        score = int(category["score"])
        level = category.get("level")
        conf = category.get("confidence") or 0
        if level is not None and level >= 4 and conf >= 0.5 and len(strengths) < 3:
            body = (
                f"{_label(category['id'])} scored {score} at level {level}. "
                f"This uses scoring-config {facts['scoring_config_version']}."
            )
            _assert_numbers_from_facts(body, facts)
            strengths.append(
                _insight(
                    category_id=category["id"],
                    title=f"{_label(category['id'])} is a measured strength",
                    body=body,
                    fix=None,
                    drill_ids=[],
                    evidence_ids=eids[:2],
                    impact=None,
                )
            )
        if level is not None and level <= 2 and conf >= 0.5:
            metric_ids = [m["id"] for m in analysis.get("metrics") or [] if m["category_id"] == category["id"]]
            attached = []
            for mid in metric_ids:
                attached.extend(drills.get(mid) or [])
            body = (
                f"{_label(category['id'])} scored {score} at level {level}. "
                f"Practice the attached drill using the timestamps in the evidence list."
            )
            _assert_numbers_from_facts(body, facts)
            weaknesses.append(
                _insight(
                    category_id=category["id"],
                    title=f"{_label(category['id'])} needs practice",
                    body=body,
                    fix="Rehearse the drill once, then re-record the same section.",
                    drill_ids=list(dict.fromkeys(attached))[:2],
                    evidence_ids=eids[:2],
                    impact=None,
                )
            )

    opportunities: list[dict[str, Any]] = []
    ranked = engine_opportunities or []
    for item in ranked[:3]:
        cid = item["category_id"]
        eids = evidence_by_cat.get(cid) or fallback_evidence
        if not eids or by_cat.get(cid, {}).get("score") is None:
            continue
        score = int(by_cat[cid]["score"])
        target = int(round(item.get("target_score") or score))
        impact = item.get("impact")
        metric_ids = [m["id"] for m in analysis.get("metrics") or [] if m["category_id"] == cid]
        attached = []
        for mid in metric_ids:
            attached.extend(drills.get(mid) or [])
        body = (
            f"{_label(cid)} is at {score}. "
            f"A target near {target} is the next practice band from the scoring config."
        )
        _assert_numbers_from_facts(body, facts)
        opportunities.append(
            _insight(
                category_id=cid,
                title=f"Practice {_label(cid)}",
                body=body,
                fix="Use the attached drill, then re-analyze the same talk.",
                drill_ids=list(dict.fromkeys(attached))[:2],
                evidence_ids=eids[:2],
                impact=None if impact is None else float(impact),
            )
        )

    overall = analysis.get("overall") or {}
    scored = facts["scored_count"]
    unavailable = facts["unavailable_count"]
    if overall.get("score") is None:
        summary = (
            f"This is a partial audio/text report. {scored} categories have scores and "
            f"{unavailable} are unavailable because their inputs were missing. "
            "No category was given an invented score."
        )
    else:
        band = overall.get("display_band")
        summary = (
            f"Overall score {int(overall['score'])} ± {int(band)} "
            f"from {scored} scored categories "
            f"(coverage {float(overall.get('coverage') or 0):.2f}, "
            f"scoring-config {facts['scoring_config_version']}). "
            f"{unavailable} categories are unavailable."
        )
    _assert_numbers_from_facts(summary, facts)
    _assert_no_emotion(summary)
    for block in strengths + weaknesses + opportunities:
        _assert_no_emotion(block["title"])
        _assert_no_emotion(block["body"])
        if block.get("fix"):
            _assert_no_emotion(block["fix"])

    analysis["insights"] = {
        "summary": summary[:1200],
        "strengths": strengths[:3],
        "weaknesses": weaknesses,
        "opportunities": opportunities[:3],
    }
    analysis.setdefault("provenance", {})
    stages = analysis["provenance"].setdefault("stages", [])
    if not any(s.get("name") == "report" for s in stages):
        stages.append({"name": "report", "version": STAGE_VERSION, "duration_s": 0.0, "status": "ok"})

    output_path = Path(output_path)
    output_path.write_text(json.dumps(analysis, indent=2, ensure_ascii=False) + "\n")
    logger.info("Wrote report %s", output_path)
    return analysis


def run_report_stage(
    *,
    output_dir: Path,
    analysis: Optional[dict[str, Any]] = None,
    packages_dir: Optional[Path] = None,
) -> dict[str, Any]:
    output_dir = Path(output_dir)
    if analysis is None:
        analysis = json.loads((output_dir / "analysis_result.json").read_text())
    packages = packages_dir or _packages_dir()
    opportunities = []
    try:
        from pipeline.stages.fusion_scoring import _ensure_scoring_path

        _ensure_scoring_path()
        from scoring import ScoringEngine

        engine = ScoringEngine("1.0.0", config_path=packages / "scoring-config")
        context = analysis.get("session", {}).get("context_type") or "keynote"
        opportunities = engine.rank_opportunities(
            [
                {
                    "id": c["id"],
                    "score": c.get("score"),
                    "confidence": c.get("confidence") or 0,
                    "applicable": c.get("applicable"),
                }
                for c in analysis.get("categories") or []
            ],
            context,
        )
    except Exception as exc:
        logger.info("Opportunity ranking skipped: %s", exc)

    report = build_report(
        analysis=analysis,
        output_path=output_dir / "report.json",
        packages_dir=packages,
        engine_opportunities=opportunities,
    )
    (output_dir / "analysis_result.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    )
    return report
