"""Tests for schema validation of scoring engine output."""

import json
from pathlib import Path
import jsonschema
from scoring import ScoringEngine


class TestSchemaValidation:
    """Test that scoring engine output validates against analysis_result schema."""
    
    def test_synthetic_payload_validates_against_schema(self):
        """Scoring engine output for synthetic metrics validates against analysis_result.v1.json."""
        # Load the analysis_result schema
        # From tests/unit/test_schema.py -> packages/scoring/tests/unit/test_schema.py
        # Go up to packages/ then to schemas/
        schema_path = (
            Path(__file__).parent.parent.parent.parent
            / "schemas"
            / "analysis_result.v1.json"
        )
        with open(schema_path) as f:
            schema = json.load(f)
        
        # Create a synthetic analysis result using the scoring engine
        engine = ScoringEngine("1.0.0")
        
        # Synthetic metrics for fluency category
        fluency_metrics = [
            {
                "id": "fl_filler_sounds_per_min",
                "raw_value": 2.0,
                "confidence": 0.9,
                "score": 85,
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
        
        # Score the category
        fluency_result = engine.score_category("fluency", fluency_metrics, "keynote")
        
        # Build a minimal but complete analysis_result payload
        analysis_result = {
            "schema_version": "1.0.0",
            "session": {
                "id": "00000000-0000-0000-0000-000000000000",
                "context_type": "keynote",
                "language": "en",
                "slot_min": 20,
                "qa_in_slot": False,
                "camera_setup": "to_camera",
                "talk_plan_id": None,
            },
            "provenance": {
                "pipeline_version": "0.1.0",
                "scoring_config_version": "1.0.0",
                "stages": [
                    {
                        "name": "scoring",
                        "version": "0.1.0",
                        "duration_s": 0.5,
                        "status": "ok",
                    }
                ],
                "models": [],
                "prompts": [],
                "generated_at": "2026-10-09T02:48:00Z",
            },
            "media": {
                "duration_s": 600.0,
                "has_video": False,
                "has_audio": True,
                "speech_span_s": 580.0,
                "fps_analyzed": None,
            },
            "quality": {
                "asr_mean_word_prob": 0.9,
                "snr_db": 25.0,
                "face_visible_ratio": None,
                "person_visible_ratio": None,
                "hands_visible_ratio": None,
                "face_px_median": None,
                "warnings": [],
            },
            "overall": {
                "score": 82,
                "level": 5,
                "coverage": 0.04,  # Just fluency (weight 4 in keynote)
                "confidence": 0.88,
                "display_band": 1,
                "partial": True,
            },
            "pillars": [
                {
                    "id": "voice",
                    "score": 82,
                    "confidence": 0.88,
                    "categories": ["fluency"],
                }
            ],
            "categories": [
                {
                    "id": "fluency",
                    "pillar": "voice",
                    "applicable": True,
                    "na_reason": None,
                    "score": int(round(fluency_result["score"])) if fluency_result["score"] is not None else None,
                    "level": fluency_result["level"],
                    "confidence": fluency_result["confidence"],
                    "confidence_label": fluency_result["confidence_label"],
                    "weight_used": 4,
                    "capped_by_gate": None,
                    "top_contributors": ["fl_filler_sounds_per_min", "fl_filler_words_per_min"],
                    "evidence_ids": [],
                    "sources": ["S12", "S21", "S33"],
                    "counterfactual": None,
                }
            ],
            "metrics": [
                {
                    "id": "fl_filler_sounds_per_min",
                    "category_id": "fluency",
                    "raw_value": 2.0,
                    "unit": "per_minute",
                    "score": 85,
                    "weight": 0.4,
                    "confidence": 0.9,
                    "included": True,
                    "basis": {"kind": "research", "source": "S12"},
                    "target_band": None,
                    "details": {},
                },
                {
                    "id": "fl_filler_words_per_min",
                    "category_id": "fluency",
                    "raw_value": 3.0,
                    "unit": "per_minute",
                    "score": 80,
                    "weight": 0.2,
                    "confidence": 0.85,
                    "included": True,
                    "basis": {"kind": "research", "source": "S12"},
                    "target_band": None,
                    "details": {},
                },
            ],
            "evidence": [],
            "insights": {
                "summary": "Strong fluency with minimal filler sounds and words.",
                "strengths": [],
                "weaknesses": [],
                "opportunities": [],
            },
            "series": {},
            "transcript_ref": "s3://bucket/session-id/transcript.json",
        }
        
        # Validate against schema
        try:
            jsonschema.validate(instance=analysis_result, schema=schema)
        except jsonschema.ValidationError as e:
            raise AssertionError(
                f"Scoring engine output does not validate against schema: {e.message}"
            ) from e
        
        # If we get here, validation passed
        assert True
