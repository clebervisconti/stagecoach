"""Plan deck review: per-slide table, storyline test, text heuristics (issue #60).

Uses python-pptx / pdftotext via pipeline.slides.deck. No live slides_v1 LLM.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from pipeline.slides.visual_aids import headline_type

NON_DATA_WORD_FLAG = 25
ANY_WORD_FLAG = 40
BULLET_FLAG = 3


def _words(text: str) -> list[str]:
    return [part for part in (text or "").replace("\n", " ").split() if part]


def _is_data_slide(text: str, word_count: int) -> bool:
    tokens = _words(text)
    if not tokens:
        return False
    digits = sum(1 for token in tokens if any(ch.isdigit() for ch in token))
    return word_count <= 12 and digits / max(len(tokens), 1) >= 0.4


def suggest_assertion_title(slide: dict[str, Any]) -> str:
    title = str(slide.get("title") or "").strip()
    body = str(slide.get("body") or slide.get("text") or "").strip()
    if headline_type(title) == "assertion":
        return title if title.endswith(".") else f"{title}."
    seed = title or (body.split(".")[0] if body else "This slide has one takeaway")
    words = _words(seed)[:12]
    sentence = " ".join(words).rstrip(".")
    if not sentence:
        sentence = "This slide has one takeaway"
    return f"{sentence}."


def flag_slide(slide: dict[str, Any]) -> list[str]:
    text = str(slide.get("text") or slide.get("body") or "")
    title = str(slide.get("title") or "")
    word_count = int(slide.get("word_count") or len(_words(text)))
    bullets = int(slide.get("bullet_count") or 0)
    issues: list[str] = []
    if not _is_data_slide(text, word_count) and word_count > NON_DATA_WORD_FLAG:
        issues.append("non-data slide over ~25 words")
    if word_count > ANY_WORD_FLAG:
        issues.append("over ~40 words")
    if bullets > BULLET_FLAG:
        issues.append("more than 3 bullets")
    if headline_type(title) != "assertion":
        issues.append("topic title; rewrite as an assertion headline")
    return issues


def headline_storyline(slides: list[dict[str, Any]]) -> dict[str, Any]:
    titles = [str(slide.get("title") or "").strip() for slide in slides]
    filled = [title for title in titles if title]
    text = " → ".join(filled)
    unique = {title.casefold() for title in filled}
    assertion_n = sum(1 for title in filled if headline_type(title) == "assertion")
    passes = len(filled) >= 2 and len(unique) >= 2 and assertion_n >= 1
    return {
        "titles": titles,
        "text": text,
        "assertion_count": assertion_n,
        "passes": passes,
        "note": "Titles in order should tell the story (headline storyline test).",
    }


def review_slides(slides: list[dict[str, Any]]) -> dict[str, Any]:
    table: list[dict[str, Any]] = []
    for slide in slides:
        issues = flag_slide(slide)
        suggested = suggest_assertion_title(slide)
        table.append(
            {
                "slide": int(slide.get("index") or len(table) + 1),
                "issue": "; ".join(issues) if issues else "ok",
                "fix": (
                    "rewrite headline / cut / move to appendix"
                    if issues
                    else "keep"
                ),
                "suggested_assertion_title": suggested,
            }
        )
    return {
        "prompt_id": "prep_slides_v1",
        "table": table,
        "storyline": headline_storyline(slides),
        "heuristics": {
            "non_data_word_flag": NON_DATA_WORD_FLAG,
            "any_word_flag": ANY_WORD_FLAG,
            "bullet_flag": BULLET_FLAG,
        },
    }


def review_deck(path: Optional[Path]) -> dict[str, Any]:
    """Extract PPTX/PDF then review. Missing path → empty table."""
    if path is None:
        return review_slides([])
    from pipeline.slides.deck import extract_deck

    extracted = extract_deck(path) or {}
    return review_slides(list(extracted.get("pages") or []))
