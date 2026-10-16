"""prep_clarify_v1: extract fields and ≤ 5 questions (SPEC §9.1 / issue #56).

Stand-in extractor in tests. Live LLM is optional via the generate hook.
"""

from __future__ import annotations

import re
from typing import Any, Callable

CRITICAL_FIELDS = ("goal", "slot_min", "audience_decision")
MAX_QUESTIONS = 5

QUESTION_BANK: dict[str, dict[str, str]] = {
    "goal": {
        "en": "What should the audience believe or do afterwards?",
        "pt-BR": "O que o público deve acreditar ou fazer depois?",
    },
    "slot_min": {
        "en": "How many minutes is the slot, and is Q&A inside it?",
        "pt-BR": "Quantos minutos tem o slot, e a Q&A entra nesse tempo?",
    },
    "audience_decision": {
        "en": "What must this audience decide or do after the talk?",
        "pt-BR": "O que este público precisa decidir ou fazer depois da fala?",
    },
    "audience_roles": {
        "en": "Who is in the room (roles and seniority)?",
        "pt-BR": "Quem está na sala (papéis e senioridade)?",
    },
    "audience_depth": {
        "en": "How technical is the audience on a 1–5 scale?",
        "pt-BR": "Qual a profundidade técnica do público (1–5)?",
    },
}

ASSUMPTIONS: dict[str, dict[str, str]] = {
    "goal": {
        "en": "Assuming the goal is to inform this audience (not stated).",
        "pt-BR": "Assumindo que o objetivo é informar este público (não informado).",
    },
    "slot_min": {
        "en": "Assuming a 20-minute slot with no Q&A inside it (not stated).",
        "pt-BR": "Assumindo um slot de 20 minutos sem Q&A (não informado).",
    },
    "audience_decision": {
        "en": "Assuming the audience must understand the recommendation (decision not stated).",
        "pt-BR": "Assumindo que o público deve entender a recomendação (decisão não informada).",
    },
    "audience_roles": {
        "en": "Assuming a mixed professional audience (roles not stated).",
        "pt-BR": "Assumindo um público profissional misto (papéis não informados).",
    },
    "audience_depth": {
        "en": "Assuming moderate technical depth (3/5) (not stated).",
        "pt-BR": "Assumindo profundidade técnica moderada (3/5) (não informada).",
    },
}


def _locale(language: str) -> str:
    return "pt-BR" if language == "pt-BR" else "en"


def extract_fields(description: str) -> dict[str, Any]:
    """Stand-in structured extract from the free-text description. No live LLM."""
    text = description or ""
    lower = text.lower()
    extracted: dict[str, Any] = {}
    slot = re.search(r"(\d{1,3})\s*(?:-|\u2013)?\s*min(?:ute)?s?", lower)
    if slot:
        extracted["slot_min"] = int(slot.group(1))
    if re.search(r"q\s*&\s*a|q and a|perguntas", lower):
        extracted["qa_in_slot"] = True
        qa = re.search(r"(\d{1,2})\s*min(?:ute)?s?\s+(?:of\s+)?(?:q\s*&\s*a|qa)", lower)
        if qa:
            extracted["qa_min"] = int(qa.group(1))
    goal = re.search(
        r"(?:goal|objetivo|so that|para que)\s*[:\-]\s*(.+?)(?:\.|$)",
        text,
        re.IGNORECASE,
    )
    if goal:
        extracted["goal"] = goal.group(1).strip()
    if re.search(r"\b(approve|decide|sign off|comprar|aprovar|decidir)\b", lower):
        extracted["audience_decision"] = "make a decision or approve a next step"
    if re.search(r"\bexec(?:utive)?|c-level|board|diretoria\b", lower):
        extracted["audience_roles"] = "executives"
        extracted["audience_depth"] = 2
    if re.search(r"\bengineer|technical|engenheir", lower):
        extracted.setdefault("audience_roles", "technical")
        extracted.setdefault("audience_depth", 4)
    return extracted


def merge_extracted(plan: dict[str, Any], extracted: dict[str, Any]) -> dict[str, Any]:
    merged = dict(plan)
    audience = dict(plan.get("audience") or {})
    if "slot_min" in extracted and not plan.get("slot_min"):
        merged["slot_min"] = extracted["slot_min"]
    if "qa_in_slot" in extracted:
        merged["qa_in_slot"] = extracted["qa_in_slot"]
    if "qa_min" in extracted and not plan.get("qa_min"):
        merged["qa_min"] = extracted["qa_min"]
    if "goal" in extracted and not plan.get("goal"):
        merged["goal"] = extracted["goal"]
    if "audience_decision" in extracted and not audience.get("decision"):
        audience["decision"] = extracted["audience_decision"]
    if "audience_roles" in extracted and not audience.get("roles"):
        audience["roles"] = extracted["audience_roles"]
    if "audience_depth" in extracted and not audience.get("technical_depth"):
        audience["technical_depth"] = extracted["audience_depth"]
    if audience:
        merged["audience"] = audience
    return merged


def missing_critical(plan: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    if not (plan.get("goal") or "").strip():
        missing.append("goal")
    if not plan.get("slot_min"):
        missing.append("slot_min")
    audience = plan.get("audience") or {}
    if not (audience.get("decision") or "").strip():
        missing.append("audience_decision")
    if not (audience.get("roles") or "").strip():
        missing.append("audience_roles")
    if audience.get("technical_depth") is None:
        missing.append("audience_depth")
    return missing


def build_questions(plan: dict[str, Any], language: str = "en") -> list[dict[str, str]]:
    loc = _locale(language)
    questions: list[dict[str, str]] = []
    for field in missing_critical(plan):
        if len(questions) >= MAX_QUESTIONS:
            break
        bank = QUESTION_BANK[field]
        questions.append({"id": field, "prompt": bank[loc]})
    return questions


def assumptions_for_skip(questions: list[dict[str, str]], language: str = "en") -> list[str]:
    loc = _locale(language)
    return [ASSUMPTIONS[q["id"]][loc] for q in questions if q["id"] in ASSUMPTIONS]


def run_clarify(
    plan: dict[str, Any],
    *,
    skip: bool = False,
    generate: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Extract fields, then ask ≤ 5 questions or record explicit assumptions."""
    description = plan.get("description") or ""
    extracted = extract_fields(description)
    if generate is not None:
        extra = generate({"description": description, "plan": plan}) or {}
        extracted = {**extracted, **extra}
    merged = merge_extracted(plan, extracted)
    questions = build_questions(merged, language=str(merged.get("language") or "en"))
    assumptions: list[str] = []
    if skip:
        assumptions = assumptions_for_skip(questions, language=str(merged.get("language") or "en"))
        questions = []
        if not merged.get("slot_min"):
            merged["slot_min"] = 20
        if not (merged.get("goal") or "").strip():
            merged["goal"] = "Inform this audience"
        audience = dict(merged.get("audience") or {})
        audience.setdefault("decision", "understand the recommendation")
        merged["audience"] = audience
    return {
        "plan": merged,
        "extracted": extracted,
        "questions": questions[:MAX_QUESTIONS],
        "assumptions": assumptions,
        "skipped": skip,
        "prompt_id": "prep_clarify_v1",
    }
