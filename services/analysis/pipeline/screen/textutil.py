"""Lexical helpers for screen flow. Overlap is cohesion, not correctness."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable, Optional

import yaml

TOKEN = re.compile(r"[A-Za-zÀ-ÿ0-9']+")

STOPWORDS = {
    "en": {
        "about",
        "after",
        "again",
        "their",
        "there",
        "these",
        "those",
        "which",
        "while",
        "would",
        "could",
        "should",
        "other",
        "being",
        "where",
        "before",
        "because",
        "through",
        "between",
    },
    "pt": {
        "sobre",
        "depois",
        "entre",
        "porque",
        "quando",
        "também",
        "tambem",
        "muito",
        "muita",
        "muitos",
        "muitas",
        "ainda",
        "então",
        "entao",
        "vocês",
        "voces",
        "você",
        "voce",
        "nossa",
        "nosso",
        "nossos",
        "nossas",
        "aquele",
        "aquela",
        "aqueles",
        "aquelas",
    },
}

PRONOUNS = {
    "en": {"you", "your", "yours", "yourself", "yourselves"},
    "pt": {"você", "vocês", "voce", "voces", "seu", "sua", "seus", "suas"},
}


def language_key(language: str) -> str:
    return "pt" if str(language or "en").lower().startswith("pt") else "en"


def load_lexicon(language: str, packages_dir: Path) -> dict[str, Any]:
    name = "pt-BR.yaml" if language_key(language) == "pt" else "en.yaml"
    path = Path(packages_dir) / "lexicons" / name
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def tokenize(text: str) -> list[str]:
    return [match.group(0).lower() for match in TOKEN.finditer(text or "")]


def _pronoun(token: str, language: str) -> Optional[str]:
    raw = token.lower()
    if "'" in raw:
        raw = raw.split("'", 1)[0]
    if raw in PRONOUNS[language_key(language)]:
        return raw
    return None


def content_tokens(text: str, language: str) -> list[str]:
    """Lowercase tokens of at least 5 characters, stopwords removed."""
    stop = STOPWORDS[language_key(language)]
    out = []
    for token in tokenize(text):
        if len(token) < 5 or token in stop:
            continue
        out.append(token)
    return out


def prefix(token: str) -> str:
    return token.lower()[:5]


def content_prefixes(text: str, language: str) -> list[str]:
    return [prefix(token) for token in content_tokens(text, language)]


def words_from_transcript(transcript: Optional[dict[str, Any]]) -> list[dict[str, Any]]:
    words: list[dict[str, Any]] = []
    if not transcript:
        return words
    for segment in transcript.get("segments") or []:
        seg_id = segment.get("id") or segment.get("seg_id")
        items = segment.get("words") or []
        if items:
            for item in items:
                token = str(item.get("word") or "").strip()
                if not token:
                    continue
                words.append(
                    {
                        "text": token,
                        "start": float(item.get("start", segment.get("start") or 0.0)),
                        "end": float(item.get("end", segment.get("end") or 0.0)),
                        "probability": float(item.get("probability", 1.0)),
                        "seg_id": seg_id,
                    }
                )
            continue
        text = str(segment.get("text") or "").strip()
        tokens = text.split()
        if not tokens:
            continue
        start = float(segment.get("start") or 0.0)
        end = float(segment.get("end") or start)
        step = (end - start) / max(len(tokens), 1)
        prob = float(segment.get("avg_probability") or segment.get("probability") or 1.0)
        for index, token in enumerate(tokens):
            words.append(
                {
                    "text": token,
                    "start": start + index * step,
                    "end": start + (index + 1) * step,
                    "probability": prob,
                    "seg_id": seg_id,
                }
            )
    return words


def speech_spans_from_alignment(payload: Optional[dict[str, Any]]) -> list[tuple[float, float]]:
    spans = []
    for row in (payload or {}).get("vad_segments") or []:
        if row.get("is_speech") is False:
            continue
        start = float(row.get("start") or 0.0)
        end = float(row.get("end") or start)
        if end > start:
            spans.append((start, end))
    spans.sort()
    return spans


def nonspeech_spans(
    speech: Iterable[tuple[float, float]],
    duration_s: float,
    *,
    min_s: float = 2.0,
) -> list[tuple[float, float]]:
    gaps = []
    cursor = 0.0
    for start, end in sorted(speech):
        if start - cursor >= min_s:
            gaps.append((cursor, start))
        cursor = max(cursor, end)
    if duration_s - cursor >= min_s:
        gaps.append((cursor, float(duration_s)))
    return gaps


def drop_hallucinated_words(
    words: list[dict[str, Any]],
    speech: list[tuple[float, float]],
    duration_s: float,
    *,
    probability_below: float = 0.4,
    nonspeech_min_s: float = 2.0,
) -> tuple[list[dict[str, Any]], int]:
    """Drop low-probability words that sit inside a VAD non-speech span ≥ 2 s.

    Whisper is known to invent text in long silences. Those words are removed
    before alignment and before any speech mask built from the transcript.
    """
    gaps = nonspeech_spans(speech, duration_s, min_s=nonspeech_min_s)
    kept = []
    dropped = 0
    for word in words:
        mid = (float(word["start"]) + float(word["end"])) / 2.0
        low = float(word.get("probability") or 0.0) < probability_below
        inside = any(start <= mid <= end for start, end in gaps)
        if low and inside:
            dropped += 1
            continue
        kept.append(word)
    return kept, dropped


def phrase_hit_times(words: list[dict[str, Any]], phrases: Iterable[str]) -> list[tuple[float, Any]]:
    items: list[tuple[str, float, Any]] = []
    for word in words:
        start = float(word["start"])
        for token in tokenize(word.get("text") or ""):
            items.append((token, start, word.get("seg_id")))
    hits: list[tuple[float, str]] = []
    for phrase in phrases:
        parts = tokenize(phrase)
        if not parts:
            continue
        width = len(parts)
        for index in range(0, len(items) - width + 1):
            if all(items[index + offset][0] == parts[offset] for offset in range(width)):
                hits.append((items[index][1], items[index][2]))
    return hits


def pronoun_tokens(words: list[dict[str, Any]], language: str) -> list[dict[str, Any]]:
    found = []
    for word in words:
        for token in tokenize(word.get("text") or ""):
            pronoun = _pronoun(token, language)
            if pronoun:
                found.append(word)
                break
    return found
