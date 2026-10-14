"""Deterministic fluency disambiguation for ambiguous filler-word candidates.

SPEC §4.4.11 and Appendix A require LLM disambiguation of né/tipo/então (pt-BR)
and like/so (en) before they count as fillers. Phase 1 CI and private beta have
no LLM key, so this module applies documented clause-context heuristics and
records `method=heuristic_v1`. An LLM pass can replace the same sidecar later.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Sequence

from .types import Word

STAGE_VERSION = "heuristic_v1"
WINDOW = 8
WORD_RE = re.compile(r"[\wÀ-ÿ'-]+", re.UNICODE)

PT_CANDIDATES = frozenset({"né", "tipo", "então", "é", "aí", "assim", "basicamente"})
EN_CANDIDATES = frozenset({"like", "so", "basically", "actually", "literally"})
PT_TIPO_LEXICAL_PREV = frozenset({"um", "uma", "o", "a", "os", "as", "este", "esta", "esse", "essa", "outro", "outra"})
PT_TIPO_LEXICAL_NEXT = frozenset({"de"})
EN_LIKE_LEXICAL_PREV = frozenset({"looks", "look", "just", "something", "seems", "felt", "sounds"})
CLAUSE_BOUNDARY = frozenset({"", ".", ",", ";", ":", "!", "?", "—"})


def normalize_token(text: str) -> str:
    return WORD_RE.sub(lambda match: match.group(0), text).strip(".,!?;:\"'“”").casefold()


def _language_bucket(language: str | None) -> str:
    value = (language or "en").casefold()
    return "pt" if value.startswith("pt") else "en"


def _candidates_for(language: str, lexicon: dict[str, Any] | None) -> set[str]:
    bucket = _language_bucket(language)
    extra = {normalize_token(item) for item in (lexicon or {}).get("filler_words_candidates") or []}
    extra -= {""}
    if bucket == "pt":
        return set(PT_CANDIDATES) | extra
    return set(EN_CANDIDATES) | extra


def _window_text(tokens: Sequence[str], start: int, end: int) -> str:
    return " ".join(tokens[start:end]).strip()


def _judge_pt(token: str, prev_token: str, next_token: str) -> tuple[bool, float]:
    if token == "né":
        # Tag-question / discourse particle; counted as filler at clause end.
        if next_token in CLAUSE_BOUNDARY:
            return True, 0.85
        return True, 0.7
    if token == "tipo":
        if next_token in PT_TIPO_LEXICAL_NEXT or prev_token in PT_TIPO_LEXICAL_PREV:
            return False, 0.85
        if next_token == "assim" or next_token in CLAUSE_BOUNDARY:
            return True, 0.9
        return True, 0.65
    if token == "então":
        if prev_token in CLAUSE_BOUNDARY:
            return False, 0.8
        if next_token in CLAUSE_BOUNDARY:
            return True, 0.75
        return False, 0.7
    if token == "é":
        if next_token in CLAUSE_BOUNDARY or next_token == "é":
            return True, 0.7
        return False, 0.8
    if token in {"aí", "assim", "basicamente"}:
        if next_token in CLAUSE_BOUNDARY:
            return True, 0.65
        return False, 0.6
    return True, 0.55


def _judge_en(token: str, prev_token: str, next_token: str) -> tuple[bool, float]:
    if token == "like":
        if prev_token in EN_LIKE_LEXICAL_PREV:
            return False, 0.85
        if next_token in CLAUSE_BOUNDARY:
            return True, 0.8
        return True, 0.65
    if token == "so":
        if prev_token in CLAUSE_BOUNDARY:
            return False, 0.8
        if next_token in CLAUSE_BOUNDARY:
            return True, 0.75
        return False, 0.65
    if token in {"basically", "actually", "literally"}:
        return True, 0.7
    return True, 0.55


def flatten_word_dicts(transcript: dict[str, Any]) -> list[dict[str, Any]]:
    words: list[dict[str, Any]] = []
    for segment in transcript.get("segments") or []:
        items = segment.get("words") or []
        if items:
            words.extend(items)
            continue
        tokens = [tok for tok in str(segment.get("text") or "").split() if tok]
        start = float(segment.get("start") or 0)
        end = float(segment.get("end") or start)
        step = (end - start) / max(len(tokens), 1)
        for index, token in enumerate(tokens):
            words.append(
                {
                    "word": token,
                    "start": start + index * step,
                    "end": start + (index + 1) * step,
                }
            )
    return words


def disambiguate_words(
    words: Sequence[dict[str, Any]],
    *,
    language: str = "en",
    lexicon: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a fluency_disambig sidecar with one hit per candidate token."""
    tokens = [normalize_token(str(item.get("word") or item.get("w") or "")) for item in words]
    bucket = _language_bucket(language)
    candidates = _candidates_for(language, lexicon)
    hits: list[dict[str, Any]] = []
    for index, token in enumerate(tokens):
        if token not in candidates:
            continue
        prev_token = tokens[index - 1] if index else ""
        next_token = tokens[index + 1] if index + 1 < len(tokens) else ""
        if bucket == "pt":
            is_filler, confidence = _judge_pt(token, prev_token, next_token)
        else:
            is_filler, confidence = _judge_en(token, prev_token, next_token)
        word = words[index]
        hits.append(
            {
                "hit_id": f"hit-{len(hits) + 1:04d}",
                "word": str(word.get("word") or word.get("w") or token),
                "token": token,
                "t_start": float(word.get("start") or 0),
                "t_end": float(word.get("end") or word.get("start") or 0),
                "context_before": _window_text(tokens, max(0, index - WINDOW), index),
                "context_after": _window_text(tokens, index + 1, index + 1 + WINDOW),
                "is_filler": is_filler,
                "confidence": confidence,
                "method": STAGE_VERSION,
            }
        )
    return {
        "version": STAGE_VERSION,
        "language": "pt-BR" if bucket == "pt" else "en",
        "disambiguations": hits,
    }


def disambiguate_transcript(
    transcript: dict[str, Any],
    lexicon: dict[str, Any] | None = None,
) -> dict[str, Any]:
    language = str(transcript.get("language") or "en")
    return disambiguate_words(flatten_word_dicts(transcript), language=language, lexicon=lexicon)


def confirmed_filler_word_objects(
    transcript: dict[str, Any],
    sidecar: dict[str, Any],
) -> list[Word]:
    """Words the heuristic counted as fillers, aligned to transcript order."""
    fillers = {
        (round(float(hit["t_start"]), 3), normalize_token(str(hit.get("word") or "")))
        for hit in sidecar.get("disambiguations") or []
        if hit.get("is_filler")
    }
    confirmed: list[Word] = []
    for item in flatten_word_dicts(transcript):
        text = str(item.get("word") or item.get("w") or "")
        start = float(item.get("start") or 0)
        end = float(item.get("end") or start)
        key = (round(start, 3), normalize_token(text))
        if key in fillers and text.strip():
            confirmed.append(
                Word(
                    text=text,
                    start=start,
                    end=end,
                    probability=float(item.get("probability") or item.get("p") or 1.0),
                )
            )
    return confirmed


def write_fluency_disambig(path: Path, sidecar: dict[str, Any]) -> Path:
    path = Path(path)
    path.write_text(json.dumps(sidecar, indent=2, ensure_ascii=False) + "\n")
    return path
