"""LLM output verification and grounding per §6.7.4 and issue #29.

- Quote verification: fuzzy match quotes against transcript segments
- Self-consistency: k=3 median with agreement confidence
- Hallucination guard: reject invalid segment IDs and out-of-range timestamps
- Evidence validation: drop unverifiable evidence and adjust confidence
"""

import hashlib
import json
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml


@dataclass
class VerificationResult:
    """Result of quote/evidence verification"""

    valid: bool
    confidence: float  # 0.0-1.0
    match_ratio: float  # Levenshtein ratio
    issue: Optional[str] = None


@dataclass
class ConsistencyResult:
    """Result of self-consistency check (k=3)"""

    median_level: float
    agreement: float  # 1 - (max - min)/4
    levels: List[float]


def normalize_text(text: str) -> str:
    """Normalize text for fuzzy matching.

    - Lowercase
    - Remove extra whitespace
    - Remove punctuation except apostrophes
    - Remove filler sounds (um, uh, éé, etc.)
    """
    text = text.lower()

    # Remove common filler sounds that might interfere with matching
    fillers = ["um", "umm", "uh", "uhh", "er", "erm", "ah", "hmm", "mm", "éé", "ééé", "eh", "ehh"]
    for filler in fillers:
        text = re.sub(rf"\b{filler}\b", "", text, flags=re.IGNORECASE)

    # Remove punctuation except apostrophes
    text = re.sub(r"[^\w\s']", " ", text)

    # Normalize whitespace
    text = " ".join(text.split())

    return text


def fuzzy_match(quote: str, segment_text: str, threshold: float = 0.9) -> Tuple[bool, float]:
    """Check if quote fuzzy-matches text within threshold.

    Uses normalized Levenshtein ratio (SequenceMatcher).

    Args:
        quote: The claimed quote
        segment_text: The text to search in
        threshold: Minimum ratio to accept (default 0.9 per §6.7.4)

    Returns:
        (is_match, ratio)
    """
    # Normalize both texts
    norm_quote = normalize_text(quote)
    norm_segment = normalize_text(segment_text)

    # Empty quote is invalid
    if not norm_quote.strip():
        return False, 0.0

    # Try exact substring match first (fast path)
    if norm_quote in norm_segment:
        return True, 1.0

    # Fuzzy match using SequenceMatcher
    # Check if quote appears as a substring with high similarity
    max_ratio = 0.0
    quote_len = len(norm_quote)

    # Sliding window over segment
    for i in range(len(norm_segment) - quote_len + 1):
        window = norm_segment[i : i + quote_len]
        ratio = SequenceMatcher(None, norm_quote, window).ratio()
        max_ratio = max(max_ratio, ratio)

        # Early exit if perfect match found
        if ratio >= 0.99:
            return True, ratio

    # Also check full segment match (in case quote is longer than expected)
    full_ratio = SequenceMatcher(None, norm_quote, norm_segment).ratio()
    max_ratio = max(max_ratio, full_ratio)

    return max_ratio >= threshold, max_ratio


def verify_quote(
    quote: str,
    seg_ids: List[str],
    segments: Dict[str, Dict[str, Any]],
    threshold: float = 0.9,
) -> VerificationResult:
    """Verify a quote against cited segments.

    Args:
        quote: The claimed quote
        seg_ids: List of segment IDs where quote should appear
        segments: Map of segment_id -> {text, start_time, end_time}
        threshold: Fuzzy match threshold (default 0.9)

    Returns:
        VerificationResult with validation outcome
    """
    if not quote or not seg_ids:
        return VerificationResult(
            valid=False,
            confidence=0.0,
            match_ratio=0.0,
            issue="Empty quote or no segment IDs",
        )

    # Check that all cited segment IDs exist
    for seg_id in seg_ids:
        if seg_id not in segments:
            return VerificationResult(
                valid=False,
                confidence=0.0,
                match_ratio=0.0,
                issue=f"Segment ID {seg_id} does not exist",
            )

    # Concatenate text from all cited segments
    combined_text = " ".join(segments[seg_id]["text"] for seg_id in seg_ids)

    # Fuzzy match
    is_match, ratio = fuzzy_match(quote, combined_text, threshold)

    if is_match:
        return VerificationResult(
            valid=True, confidence=ratio, match_ratio=ratio, issue=None
        )
    else:
        return VerificationResult(
            valid=False,
            confidence=0.0,
            match_ratio=ratio,
            issue=f"Quote does not match segment text (ratio={ratio:.3f}, threshold={threshold})",
        )


def verify_evidence_list(
    evidence_items: List[Dict[str, Any]],
    segments: Dict[str, Dict[str, Any]],
    threshold: float = 0.9,
) -> Tuple[List[Dict[str, Any]], float]:
    """Verify a list of evidence items and filter invalid ones.

    Args:
        evidence_items: List of evidence dicts with 'quote' and 'seg_id' or 'seg_ids'
        segments: Segment map
        threshold: Fuzzy match threshold

    Returns:
        (valid_evidence_list, confidence_factor)
        confidence_factor = ratio of valid evidence
    """
    if not evidence_items:
        return [], 0.0

    valid_evidence = []

    for item in evidence_items:
        quote = item.get("quote", "")

        # Handle both seg_id (single) and seg_ids (list)
        seg_ids = item.get("seg_ids")
        if not seg_ids:
            seg_id = item.get("seg_id")
            seg_ids = [seg_id] if seg_id else []

        result = verify_quote(quote, seg_ids, segments, threshold)

        if result.valid:
            valid_evidence.append(item)

    # Confidence factor = share of valid evidence
    confidence_factor = len(valid_evidence) / len(evidence_items) if evidence_items else 0.0

    return valid_evidence, confidence_factor


def check_self_consistency(levels: List[float]) -> ConsistencyResult:
    """Compute self-consistency from k=3 level samples.

    Per §6.7.4:
    - Use median level
    - Agreement = 1 - (max - min)/4

    Args:
        levels: List of 3 level values (1.0-5.0)

    Returns:
        ConsistencyResult with median and agreement
    """
    if len(levels) != 3:
        raise ValueError(f"Expected exactly 3 levels, got {len(levels)}")

    for level in levels:
        if not (1.0 <= level <= 5.0):
            raise ValueError(f"Level {level} out of range [1.0, 5.0]")

    # Sort to find median
    sorted_levels = sorted(levels)
    median_level = sorted_levels[1]  # Middle value

    # Agreement
    level_range = max(levels) - min(levels)
    agreement = 1.0 - (level_range / 4.0)
    agreement = max(0.0, min(1.0, agreement))  # Clamp to [0, 1]

    return ConsistencyResult(
        median_level=median_level, agreement=agreement, levels=sorted_levels
    )


def pull_extreme_level_toward_center(
    level: float, valid_evidence_count: int, threshold: int = 2
) -> Tuple[float, bool]:
    """Pull extreme levels (≤2 or 5) toward 3 if insufficient evidence.

    Per §6.7.4: "If a Level ≤ 2 or Level 5 judgment ends up with fewer than 2
    valid evidence items, pull it toward 3 by half a level and flag it."

    Args:
        level: The LLM-assigned level
        valid_evidence_count: Number of valid evidence items
        threshold: Minimum evidence needed (default 2)

    Returns:
        (adjusted_level, was_adjusted)
    """
    if valid_evidence_count >= threshold:
        return level, False

    # Check if extreme
    if level <= 2.0 or level >= 5.0:
        # Pull toward 3 by 0.5
        if level < 3.0:
            adjusted = min(level + 0.5, 3.0)
        else:
            adjusted = max(level - 0.5, 3.0)

        return adjusted, True

    return level, False


def validate_segment_ids(
    seg_ids: List[str], valid_segment_ids: set
) -> Tuple[bool, Optional[str]]:
    """Check that all segment IDs exist.

    Per §6.7.4 hallucination guard: "reject outputs that reference segment
    IDs that don't exist."

    Args:
        seg_ids: List of segment IDs to check
        valid_segment_ids: Set of known segment IDs

    Returns:
        (all_valid, error_message)
    """
    for seg_id in seg_ids:
        if seg_id not in valid_segment_ids:
            return False, f"Unknown segment ID: {seg_id}"

    return True, None


def validate_timestamps(
    segments: List[Dict[str, Any]], max_duration_s: float
) -> Tuple[bool, Optional[str]]:
    """Check that timestamps are within media duration.

    Per §6.7.4: "Reject timestamps outside the media duration."

    Args:
        segments: List of segments with start_time and end_time
        max_duration_s: Maximum media duration in seconds

    Returns:
        (all_valid, error_message)
    """
    for seg in segments:
        if "start_time" in seg and seg["start_time"] > max_duration_s:
            return False, f"Timestamp {seg['start_time']} exceeds duration {max_duration_s}"

        if "end_time" in seg and seg["end_time"] > max_duration_s:
            return False, f"Timestamp {seg['end_time']} exceeds duration {max_duration_s}"

    return True, None


def load_forbidden_terms(language: str) -> List[str]:
    """Load forbidden emotional inference terms for the language.

    Per §5.3 and issue #29: no emotion inference.

    Args:
        language: en or pt-BR

    Returns:
        List of forbidden terms (lowercase)
    """
    # These are terms that imply emotion inference and must not appear in
    # LLM output text (rationales, explanations, etc.)
    forbidden = {
        "en": [
            "happy",
            "sad",
            "angry",
            "anxious",
            "fearful",
            "joyful",
            "depressed",
            "frustrated",
            "excited",
            "nervous",
            "confident",  # ambiguous: "sounds confident" is OK, "feels confident" is not
            "feels",
            "feeling",
        ],
        "pt-BR": [
            "feliz",
            "triste",
            "zangado",
            "ansioso",
            "com medo",
            "frustrado",
            "animado",
            "nervoso",
            "confiante",
            "sente",
            "sentindo",
        ],
    }

    return forbidden.get(language, [])


def check_for_emotion_inference(text: str, language: str) -> Tuple[bool, List[str]]:
    """Check if text contains forbidden emotion-inferring terms.

    Per SPEC §5.3: "The app describes observable expressions and vocal signals.
    It does not read minds."
    
    Special handling for context-dependent terms:
    - "animado/animated" in phrases like "gestos animados"/"animated gestures" is OK
    - "animado/excited" describing the speaker's state is forbidden

    Args:
        text: Text to check (e.g., LLM rationale)
        language: en or pt-BR

    Returns:
        (has_forbidden_terms, list_of_found_terms)
    """
    forbidden = load_forbidden_terms(language)
    text_lower = text.lower()

    found = []
    for term in forbidden:
        if term in text_lower:
            # Context-aware filtering for ambiguous terms
            if term in ["animado", "animated", "excited"]:
                # Check if used in acceptable phrases describing delivery
                acceptable_contexts = [
                    "gestos animados", "gestos animated",  # animated gestures
                    "voz animada", "animated voice",  # animated voice
                    "ritmo animado", "animated pace",  # animated pace
                    "entrega animada", "animated delivery",  # animated delivery
                ]
                # If any acceptable phrase is present, skip this term
                if any(ctx in text_lower for ctx in acceptable_contexts):
                    continue
            
            found.append(term)

    return len(found) > 0, found
