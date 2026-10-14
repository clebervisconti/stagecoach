"""Tests for LLM verification logic per issue #29.

Tests:
- Quote verification with fuzzy matching
- Self-consistency k=3
- Extreme level adjustment
- Segment ID validation
- Timestamp validation
- Forbidden emotion terms
"""

import pytest

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from llm.verification import (
    check_for_emotion_inference,
    check_self_consistency,
    fuzzy_match,
    normalize_text,
    pull_extreme_level_toward_center,
    validate_segment_ids,
    validate_timestamps,
    verify_evidence_list,
    verify_quote,
)


class TestNormalization:
    """Test text normalization for fuzzy matching"""

    def test_normalize_basic(self):
        text = "Hello, World! This is a Test."
        normalized = normalize_text(text)
        assert normalized == "hello world this is a test"

    def test_normalize_removes_fillers(self):
        text = "Um, so like, uh, this is the point"
        normalized = normalize_text(text)
        # Should remove um, uh
        assert "um" not in normalized
        assert "uh" not in normalized
        # "so" and "like" are ambiguous and kept
        assert "so" in normalized
        assert "like" in normalized

    def test_normalize_portuguese_fillers(self):
        text = "éé, então, tipo assim, né"
        normalized = normalize_text(text)
        # Should remove éé
        assert "éé" not in normalized

    def test_normalize_extra_whitespace(self):
        text = "Multiple   spaces    here"
        normalized = normalize_text(text)
        assert "  " not in normalized


class TestFuzzyMatch:
    """Test quote fuzzy matching per §6.7.4 (≥0.9 threshold)"""

    def test_exact_match(self):
        quote = "This is the exact quote"
        segment = "And then he said: This is the exact quote. Right?"
        is_match, ratio = fuzzy_match(quote, segment)
        assert is_match
        assert ratio == 1.0

    def test_close_match_with_fillers(self):
        quote = "Last year our team spent 4,000 hours on incidents"
        segment = "Um, last year our team spent, uh, 4,000 hours on incidents"
        is_match, ratio = fuzzy_match(quote, segment, threshold=0.9)
        assert is_match
        assert ratio >= 0.9

    def test_mismatch(self):
        quote = "This is completely different"
        segment = "Nothing related to the quote at all"
        is_match, ratio = fuzzy_match(quote, segment, threshold=0.9)
        assert not is_match
        assert ratio < 0.9

    def test_partial_match_below_threshold(self):
        quote = "The quick brown fox jumps"
        segment = "The quick red fox runs"
        is_match, ratio = fuzzy_match(quote, segment, threshold=0.9)
        # Some words match but not enough
        assert not is_match or ratio < 1.0

    def test_case_insensitive(self):
        quote = "HELLO WORLD"
        segment = "hello world"
        is_match, ratio = fuzzy_match(quote, segment)
        assert is_match
        assert ratio == 1.0

    def test_empty_quote(self):
        quote = ""
        segment = "Some text"
        is_match, ratio = fuzzy_match(quote, segment)
        assert not is_match
        assert ratio == 0.0


class TestQuoteVerification:
    """Test verify_quote with segment map"""

    def test_verify_valid_quote(self):
        quote = "Good morning, everyone"
        seg_ids = ["S0001"]
        segments = {
            "S0001": {"text": "Good morning, everyone. Um, thanks for having me.", "start_time": 0.0, "end_time": 5.0}
        }

        result = verify_quote(quote, seg_ids, segments, threshold=0.9)
        assert result.valid
        assert result.match_ratio >= 0.9

    def test_verify_multi_segment_quote(self):
        quote = "First part and second part"
        seg_ids = ["S0001", "S0002"]
        segments = {
            "S0001": {"text": "First part", "start_time": 0.0, "end_time": 2.0},
            "S0002": {"text": "and second part", "start_time": 2.0, "end_time": 4.0},
        }

        result = verify_quote(quote, seg_ids, segments, threshold=0.9)
        assert result.valid

    def test_verify_unknown_segment_id(self):
        quote = "Some quote"
        seg_ids = ["S9999"]  # Doesn't exist
        segments = {"S0001": {"text": "Different text", "start_time": 0.0, "end_time": 2.0}}

        result = verify_quote(quote, seg_ids, segments)
        assert not result.valid
        assert "does not exist" in result.issue

    def test_verify_quote_mismatch(self):
        quote = "This quote is not in the segment"
        seg_ids = ["S0001"]
        segments = {"S0001": {"text": "Completely different text", "start_time": 0.0, "end_time": 2.0}}

        result = verify_quote(quote, seg_ids, segments, threshold=0.9)
        assert not result.valid
        assert result.match_ratio < 0.9


class TestEvidenceListVerification:
    """Test verify_evidence_list"""

    def test_verify_all_valid(self):
        evidence = [
            {"seg_id": "S0001", "quote": "Good morning"},
            {"seg_id": "S0002", "quote": "Thank you"},
        ]
        segments = {
            "S0001": {"text": "Good morning, everyone", "start_time": 0.0, "end_time": 2.0},
            "S0002": {"text": "Thank you for coming", "start_time": 2.0, "end_time": 4.0},
        }

        valid_evidence, confidence = verify_evidence_list(evidence, segments)
        assert len(valid_evidence) == 2
        assert confidence == 1.0

    def test_verify_partial_valid(self):
        evidence = [
            {"seg_id": "S0001", "quote": "Good morning"},
            {"seg_id": "S0002", "quote": "This quote does not match at all"},
        ]
        segments = {
            "S0001": {"text": "Good morning, everyone", "start_time": 0.0, "end_time": 2.0},
            "S0002": {"text": "Thank you for coming", "start_time": 2.0, "end_time": 4.0},
        }

        valid_evidence, confidence = verify_evidence_list(evidence, segments)
        assert len(valid_evidence) == 1
        assert confidence == 0.5  # 1/2

    def test_verify_empty_list(self):
        evidence = []
        segments = {}

        valid_evidence, confidence = verify_evidence_list(evidence, segments)
        assert len(valid_evidence) == 0
        assert confidence == 0.0


class TestSelfConsistency:
    """Test k=3 self-consistency per §6.7.4"""

    def test_perfect_agreement(self):
        levels = [4.0, 4.0, 4.0]
        result = check_self_consistency(levels)
        assert result.median_level == 4.0
        assert result.agreement == 1.0  # 1 - (0/4) = 1.0

    def test_moderate_agreement(self):
        levels = [3.0, 3.5, 4.0]
        result = check_self_consistency(levels)
        assert result.median_level == 3.5
        # Agreement = 1 - (4.0 - 3.0)/4 = 1 - 0.25 = 0.75
        assert result.agreement == 0.75

    def test_low_agreement(self):
        levels = [2.0, 3.0, 5.0]
        result = check_self_consistency(levels)
        assert result.median_level == 3.0
        # Agreement = 1 - (5.0 - 2.0)/4 = 1 - 0.75 = 0.25
        assert result.agreement == 0.25

    def test_invalid_count(self):
        with pytest.raises(ValueError, match="Expected exactly 3 levels"):
            check_self_consistency([3.0, 4.0])

    def test_out_of_range(self):
        with pytest.raises(ValueError, match="out of range"):
            check_self_consistency([0.5, 3.0, 4.0])


class TestExtremeLevelAdjustment:
    """Test pulling extreme levels toward 3 with insufficient evidence"""

    def test_low_level_with_insufficient_evidence(self):
        adjusted, was_adjusted = pull_extreme_level_toward_center(1.5, valid_evidence_count=1)
        assert was_adjusted
        assert adjusted == 2.0  # 1.5 + 0.5

    def test_high_level_with_insufficient_evidence(self):
        adjusted, was_adjusted = pull_extreme_level_toward_center(5.0, valid_evidence_count=0)
        assert was_adjusted
        assert adjusted == 4.5  # 5.0 - 0.5

    def test_level_2_with_insufficient_evidence(self):
        adjusted, was_adjusted = pull_extreme_level_toward_center(2.0, valid_evidence_count=1)
        assert was_adjusted
        assert adjusted == 2.5

    def test_mid_level_not_adjusted(self):
        adjusted, was_adjusted = pull_extreme_level_toward_center(3.0, valid_evidence_count=1)
        assert not was_adjusted
        assert adjusted == 3.0

    def test_sufficient_evidence_not_adjusted(self):
        adjusted, was_adjusted = pull_extreme_level_toward_center(1.5, valid_evidence_count=2)
        assert not was_adjusted
        assert adjusted == 1.5


class TestHallucinationGuard:
    """Test segment ID and timestamp validation"""

    def test_valid_segment_ids(self):
        seg_ids = ["S0001", "S0002", "S0042"]
        valid_set = {"S0001", "S0002", "S0042", "S0100"}

        is_valid, error = validate_segment_ids(seg_ids, valid_set)
        assert is_valid
        assert error is None

    def test_invalid_segment_id(self):
        seg_ids = ["S0001", "S9999"]
        valid_set = {"S0001", "S0002"}

        is_valid, error = validate_segment_ids(seg_ids, valid_set)
        assert not is_valid
        assert "S9999" in error

    def test_valid_timestamps(self):
        segments = [
            {"start_time": 0.0, "end_time": 10.0},
            {"start_time": 10.0, "end_time": 20.0},
        ]
        max_duration = 30.0

        is_valid, error = validate_timestamps(segments, max_duration)
        assert is_valid
        assert error is None

    def test_timestamp_exceeds_duration(self):
        segments = [
            {"start_time": 0.0, "end_time": 10.0},
            {"start_time": 10.0, "end_time": 100.0},  # Exceeds max
        ]
        max_duration = 30.0

        is_valid, error = validate_timestamps(segments, max_duration)
        assert not is_valid
        assert "100" in error


class TestEmotionInference:
    """Test forbidden emotion term detection per §5.3"""

    def test_english_forbidden_terms(self):
        text = "The speaker sounds happy and confident"
        has_forbidden, terms = check_for_emotion_inference(text, "en")
        assert has_forbidden
        assert "happy" in terms

    def test_portuguese_forbidden_terms(self):
        text = "O palestrante parece triste e ansioso"
        has_forbidden, terms = check_for_emotion_inference(text, "pt-BR")
        assert has_forbidden
        assert "triste" in terms or "ansioso" in terms

    def test_no_forbidden_terms(self):
        text = "The speaker uses clear language and strong examples"
        has_forbidden, terms = check_for_emotion_inference(text, "en")
        assert not has_forbidden
        assert len(terms) == 0

    def test_case_insensitive(self):
        text = "The speaker is HAPPY and EXCITED"
        has_forbidden, terms = check_for_emotion_inference(text, "en")
        assert has_forbidden

    def test_partial_word_match(self):
        # "feeling" contains "feel" which is forbidden
        text = "The speaker has a feeling this will work"
        has_forbidden, terms = check_for_emotion_inference(text, "en")
        assert has_forbidden
        assert "feeling" in terms
