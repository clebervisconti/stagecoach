"""Phase 3 exit: exec-briefing plan AC, authz, audit hooks (issue #70)."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "packages" / "scoring"))

from pipeline.prep_message import MAX_CORE_WORDS, run_message
from pipeline.prep_structure import run_structure
from scoring.time_budget import CutItem, build_cut_list, build_time_budget, rehearsal_plan


def test_exec_briefing_plan_acceptance():
    plan = {
        "title": "Approve the pilot",
        "description": "A 20-minute executive briefing so the board will approve the pilot.",
        "context_type": "exec_briefing",
        "slot_min": 20,
        "language": "en",
        "audience": {"roles": "executives", "decision": "approve the pilot"},
    }
    message = run_message(plan)
    assert len(message["candidates"]) == 3
    assert all(row["word_count"] <= MAX_CORE_WORDS for row in message["candidates"])

    structure = run_structure(plan)
    assert any(row["id"] == "scr" for row in structure["options"])

    budget = build_time_budget(slot_min=20)
    assert budget.available_speaking_min == pytest.approx(18.0)
    assert budget.max_script_words == pytest.approx(2340.0)

    cuts = [
        row
        for row in build_cut_list(
            [
                CutItem("hook", "hook", "cold open"),
                CutItem("aside", "off_message", "picnic"),
                CutItem("ex2", "extra_example", "second story"),
                CutItem("hist", "background", "founded 1998"),
                CutItem("table", "detailed_data", "full table"),
                CutItem("flex", "collapsible", "appendix"),
            ]
        )
        if row.action == "cut"
    ]
    assert [row.kind for row in cuts] == [
        "off_message",
        "extra_example",
        "background",
        "detailed_data",
        "collapsible",
    ]

    steps = rehearsal_plan(date(2026, 11, 15), context_type="exec_briefing")
    assert steps[-1].date == date(2026, 11, 15)
    assert steps[0].date is not None and steps[0].date < steps[-1].date


def test_cross_user_plan_is_404():
    text = (ROOT / "services" / "api" / "app" / "plans_service.py").read_text(encoding="utf-8")
    assert "def require_owned" in text
    assert "HTTP_404_NOT_FOUND" in text


def test_ci_has_npm_and_pip_audit():
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "npm audit" in ci
    assert "pip-audit" in ci
    # trivy is not in this workflow; flagged for the owner in ADR-054.


def test_readme_documents_compose_and_make_dev():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "make dev" in readme
    assert "docker compose" in readme.lower() or "Docker Compose" in readme
