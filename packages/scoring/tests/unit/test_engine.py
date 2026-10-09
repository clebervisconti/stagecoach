"""Tests for the main scoring engine."""

import pytest
from scoring import ScoringEngine


class TestScoringEngine:
    """Test the main ScoringEngine class."""
    
    def test_engine_loads_config(self):
        """Engine loads a config version."""
        engine = ScoringEngine("1.0.0")
        assert engine.version == "1.0.0"
        assert engine.config["version"] == "1.0.0"
    
    def test_engine_fails_on_missing_version(self):
        """Engine raises if config version doesn't exist."""
        with pytest.raises(ValueError, match="not found"):
            ScoringEngine("99.99.99")
    
    def test_score_metric_with_curve(self):
        """Score a metric with a curve."""
        engine = ScoringEngine("1.0.0")
        
        # Filler sounds per minute
        result = engine.score_metric(
            "fl_filler_sounds_per_min",
            raw_value=7.2,
            confidence=0.85,
            category_id="fluency",
        )
        
        assert result["included"] is True
        assert result["inclusion_factor"] == 1.0  # c=0.85 >= 0.6
        assert 30 < result["score"] < 40  # Between 8/min (35) and 5/min (55)
    
    def test_score_metric_llm_level(self):
        """Score an LLM-judged metric."""
        engine = ScoringEngine("1.0.0")
        
        # LLM level 3 → score = 20*3 - 10 = 50
        result = engine.score_metric(
            "cm_message_identifiable",
            raw_value=3.0,
            confidence=0.9,
            category_id="core_message",
        )
        
        assert result["score"] == 50
        assert result["included"] is True
    
    def test_score_metric_with_mapping(self):
        """Score a categorical metric with a mapping."""
        engine = ScoringEngine("1.0.0")
        
        result = engine.score_metric(
            "st_recap_present",
            raw_value="present",
            confidence=1.0,
            category_id="structure",
        )
        
        assert result["score"] == 90
    
    def test_score_metric_low_confidence_excluded(self):
        """Low confidence metrics are excluded."""
        engine = ScoringEngine("1.0.0")
        
        result = engine.score_metric(
            "fl_filler_sounds_per_min",
            raw_value=2.0,
            confidence=0.3,  # Below 0.4 threshold
            category_id="fluency",
        )
        
        assert result["included"] is False
        assert result["inclusion_factor"] == 0.0
    
    def test_score_category(self):
        """Score a category from metrics."""
        engine = ScoringEngine("1.0.0")
        
        # Fluency with two metrics
        metrics = [
            {
                "id": "fl_filler_sounds_per_min",
                "raw_value": 2.0,
                "confidence": 0.9,
                "score": 85,  # From curve
                "inclusion_factor": 1.0,
            },
            {
                "id": "fl_filler_words_per_min",
                "raw_value": 3.0,
                "confidence": 0.85,
                "score": 80,
                "inclusion_factor": 1.0,
            },
        ]
        
        result = engine.score_category("fluency", metrics, "keynote")
        
        assert result["applicable"] is True
        assert result["score"] is not None
        assert 80 <= result["score"] <= 85
        assert result["level"] == 5  # Score in 80-100 range
        assert result["confidence"] > 0.8
    
    def test_score_overall(self):
        """Score overall from categories."""
        engine = ScoringEngine("1.0.0")
        
        categories = [
            {
                "id": "fluency",
                "score": 85,
                "confidence": 0.9,
                "applicable": True,
            },
            {
                "id": "pace_pausing",
                "score": 70,
                "confidence": 0.85,
                "applicable": True,
            },
            {
                "id": "facial_affect",
                "score": 50,
                "confidence": 0.3,  # Too low, excluded
                "applicable": True,
            },
        ]
        
        result = engine.score_overall(categories, "keynote")
        
        assert result["score"] is not None
        # Fluency weight=4, Pace weight=5, Facial excluded
        # (85*4 + 70*5) / (4+5) = (340 + 350) / 9 = 76.67
        assert 76 <= result["score"] <= 77
        assert result["level"] == 4
        assert result["coverage"] < 1.0  # Not all categories included
    
    def test_rank_opportunities(self):
        """Rank improvement opportunities."""
        engine = ScoringEngine("1.0.0")
        
        categories = [
            {
                "id": "fluency",
                "score": 85,
                "confidence": 0.9,
                "applicable": True,
            },
            {
                "id": "pace_pausing",
                "score": 50,
                "confidence": 0.85,
                "applicable": True,
            },
            {
                "id": "storytelling",
                "score": 40,
                "confidence": 0.8,
                "applicable": True,
            },
        ]
        
        opportunities = engine.rank_opportunities(
            categories,
            "keynote",
            focus_areas=["storytelling"],
        )
        
        # Storytelling should rank high due to:
        # - Low score (40)
        # - High weight in keynote (10)
        # - Focus area boost
        assert len(opportunities) > 0
        assert opportunities[0]["category_id"] in ["storytelling", "pace_pausing"]
        
        # Check that storytelling got the focus boost
        sto_opp = next(o for o in opportunities if o["category_id"] == "storytelling")
        assert sto_opp["is_focus_area"] is True
