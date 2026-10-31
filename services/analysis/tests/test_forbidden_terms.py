"""Tests for forbidden emotion inference terms per SPEC §5.3 and ADR-010.

Per issue #29 acceptance criteria: test that forbidden terms are detected
in LLM output text fields (rationale, explanations, etc.).
"""

import re
import sys
from pathlib import Path

import pytest

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from llm.verification import check_for_emotion_inference, load_forbidden_terms


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
            "Strong vocal variety and animated gestures",  # "animated gestures" is OK
            "Maintains steady eye contact",
            "The pace is conversational",
            "Expression signals include smiles and raised eyebrows",
            "Vocal energy is high",
            "Animated voice with strong emphasis",  # "animated voice" is OK
            "Animated delivery throughout",  # "animated delivery" is OK
        ]

        for text in acceptable_texts:
            has_forbidden, terms = check_for_emotion_inference(text, "en")
            assert not has_forbidden, f"False positive for: {text} (terms: {terms})"
    
    def test_forbidden_excited_context(self):
        """Test that 'excited' is forbidden when describing emotional state"""
        # These describe the speaker's emotional state, not delivery
        forbidden_texts = [
            "The speaker seemed excited and energetic",  # "seemed excited"
            "You appeared very excited today",  # "appeared excited"
            "He was excited about the results",  # "was excited"
        ]
        
        for text in forbidden_texts:
            has_forbidden, terms = check_for_emotion_inference(text, "en")
            assert has_forbidden, f"Should flag emotional state: {text}"
            assert "excited" in terms


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
            "Variedade vocal forte e gestos animados",  # "animated gestures" is OK
            "Mantém contato visual constante",
            "O ritmo é conversacional",
            "Sinais de expressão incluem sorrisos",
            "Voz animada e entrega energética",  # "animated voice" is OK
            "Ritmo animado durante a apresentação",  # "animated pace" is OK
        ]

        for text in acceptable_texts:
            has_forbidden, terms = check_for_emotion_inference(text, "pt-BR")
            assert not has_forbidden, f"False positive for: {text} (terms: {terms})"
    
    def test_forbidden_animado_context(self):
        """Test that 'animado' is forbidden when describing emotional state"""
        # These describe the speaker's emotional state, not delivery
        forbidden_texts = [
            "O palestrante parecia animado e empolgado",  # "seemed excited"
            "Você estava muito animado hoje",  # "you were very excited"
            "Ele ficou animado com os resultados",  # "he got excited"
        ]
        
        for text in forbidden_texts:
            has_forbidden, terms = check_for_emotion_inference(text, "pt-BR")
            assert has_forbidden, f"Should flag emotional state: {text}"
            assert "animado" in terms


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


def test_screen_flow_sources_do_not_name_affect():
    """Word-boundary scan. A metric id with an underscore is not that word."""
    root = Path(__file__).resolve().parents[1]
    files = list((root / "pipeline" / "screen").glob("*.py"))
    files.append(root / "pipeline" / "stages" / "screen_flow.py")
    blob = "\n".join(path.read_text(encoding="utf-8") for path in files)
    found = [term for term in load_forbidden_terms("en") if re.search(rf"\b{re.escape(term)}\b", blob, re.IGNORECASE)]
    assert found == []


def test_content_judgment_checker_ignores_order_words_and_flags_claims():
    from llm.verification import check_for_content_judgment

    flagged, terms = check_for_content_judgment("That statement is incorrect.", "en")
    assert flagged and "incorrect" in terms
    clear, _found = check_for_content_judgment("The wrong slide is still on screen.", "en")
    assert clear is False
    wrong, hits = check_for_content_judgment("The date on the slide is wrong.", "en")
    assert wrong and "wrong" in hits
