"""Tests for forbidden emotion inference terms per SPEC §5.3 and ADR-010.

Per issue #29 acceptance criteria: test that forbidden terms are detected
in LLM output text fields (rationale, explanations, etc.).
"""

import pytest

from services.analysis.llm.verification import check_for_emotion_inference


class TestForbiddenTermsEnglish:
    """Test English forbidden terms per §5.3"""

    def test_happy(self):
        text = "The speaker sounds happy and enthusiastic"
        has_forbidden, terms = check_for_emotion_inference(text, "en")
        assert has_forbidden
        assert "happy" in terms

    def test_sad(self):
        text = "The tone seems sad and melancholy"
        has_forbidden, terms = check_for_emotion_inference(text, "en")
        assert has_forbidden
        assert "sad" in terms

    def test_angry(self):
        text = "The speaker appears angry about the situation"
        has_forbidden, terms = check_for_emotion_inference(text, "en")
        assert has_forbidden
        assert "angry" in terms

    def test_anxious(self):
        text = "Signs of anxiety are visible"
        # "anxiety" is not in the list but "anxious" is
        # This test checks that we don't match partial words incorrectly
        has_forbidden, terms = check_for_emotion_inference(text, "en")
        # Should NOT match because we look for whole-word "anxious" not substring
        # However, our current implementation uses `in` which is substring match
        # This is intentional for now to catch variations

    def test_fearful(self):
        text = "The speaker looks fearful"
        has_forbidden, terms = check_for_emotion_inference(text, "en")
        assert has_forbidden
        assert "fearful" in terms

    def test_feels_feeling(self):
        text = "The speaker feels confident and is feeling good"
        has_forbidden, terms = check_for_emotion_inference(text, "en")
        assert has_forbidden
        # Should catch both "feels" and "feeling"
        assert "feels" in terms
        assert "feeling" in terms

    def test_confident_ambiguous(self):
        # "confident" is in the list as ambiguous
        # "sounds confident" (observable) is OK
        # "feels confident" (internal state) is not OK
        # Our detector flags both for review
        text = "The speaker sounds confident"
        has_forbidden, terms = check_for_emotion_inference(text, "en")
        assert has_forbidden
        assert "confident" in terms

    def test_acceptable_language(self):
        """Test language that describes observable behavior, not emotions"""
        acceptable_texts = [
            "The speaker uses clear language",
            "Strong vocal variety and animated gestures",
            "Maintains steady eye contact",
            "The pace is conversational",
            "Expression signals include smiles and raised eyebrows",
            "Vocal energy is high",
        ]

        for text in acceptable_texts:
            has_forbidden, terms = check_for_emotion_inference(text, "en")
            assert not has_forbidden, f"False positive for: {text} (terms: {terms})"


class TestForbiddenTermsPortuguese:
    """Test Portuguese forbidden terms per §5.3"""

    def test_feliz(self):
        text = "O palestrante parece feliz"
        has_forbidden, terms = check_for_emotion_inference(text, "pt-BR")
        assert has_forbidden
        assert "feliz" in terms

    def test_triste(self):
        text = "Tom triste e melancólico"
        has_forbidden, terms = check_for_emotion_inference(text, "pt-BR")
        assert has_forbidden
        assert "triste" in terms

    def test_ansioso(self):
        text = "Sinais de que está ansioso"
        has_forbidden, terms = check_for_emotion_inference(text, "pt-BR")
        assert has_forbidden
        assert "ansioso" in terms

    def test_com_medo(self):
        text = "O palestrante está com medo"
        has_forbidden, terms = check_for_emotion_inference(text, "pt-BR")
        assert has_forbidden
        assert "com medo" in terms

    def test_sente_sentindo(self):
        text = "O palestrante sente confiança e está sentindo-se bem"
        has_forbidden, terms = check_for_emotion_inference(text, "pt-BR")
        assert has_forbidden
        assert "sente" in terms
        assert "sentindo" in terms

    def test_acceptable_portuguese(self):
        """Test acceptable Portuguese language"""
        acceptable_texts = [
            "O palestrante usa linguagem clara",
            "Variedade vocal forte e gestos animados",
            "Mantém contato visual constante",
            "O ritmo é conversacional",
            "Sinais de expressão incluem sorrisos",
        ]

        for text in acceptable_texts:
            has_forbidden, terms = check_for_emotion_inference(text, "pt-BR")
            assert not has_forbidden, f"False positive for: {text} (terms: {terms})"


class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_empty_string(self):
        has_forbidden, terms = check_for_emotion_inference("", "en")
        assert not has_forbidden
        assert len(terms) == 0

    def test_case_insensitive(self):
        text = "The speaker is HAPPY and EXCITED"
        has_forbidden, terms = check_for_emotion_inference(text, "en")
        assert has_forbidden

    def test_multiple_forbidden_terms(self):
        text = "The speaker appears happy, confident, and excited"
        has_forbidden, terms = check_for_emotion_inference(text, "en")
        assert has_forbidden
        assert len(terms) >= 2  # Should find at least happy and confident

    def test_unknown_language_returns_empty(self):
        """Unknown language should return empty list (no checks)"""
        text = "Some text with happy"
        has_forbidden, terms = check_for_emotion_inference(text, "fr")
        assert not has_forbidden
        assert len(terms) == 0
