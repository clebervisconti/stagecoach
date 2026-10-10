"""Tests for content_llm stage per issues #27, #28, #29.

Tests LLM prompts with mock/cassette mode (no live API key needed in CI).
"""

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from llm import LLMClient, LLMResponse, UsageStats
from pipeline.stages.content_llm import (
    format_timestamp,
    format_transcript_for_prompt,
    load_segments_from_transcript,
)


@pytest.fixture
def synthetic_transcript_path():
    """Path to synthetic transcript fixture"""
    return Path(__file__).parent / "fixtures" / "synthetic_transcript.json"


@pytest.fixture
def output_dir(tmp_path):
    """Temporary output directory"""
    return tmp_path


class TestTranscriptLoading:
    """Test transcript loading and formatting"""

    def test_load_segments(self, synthetic_transcript_path):
        segments, segment_map = load_segments_from_transcript(synthetic_transcript_path)

        assert len(segments) == 24
        assert len(segment_map) == 24

        # Check first segment
        assert segments[0].seg_id == "S0001"
        assert segments[0].text == "Good morning, everyone. Thank you for having me today."
        assert segments[0].start_time == 0.0
        assert segments[0].end_time == 5.2

        # Check segment map
        assert "S0001" in segment_map
        assert segment_map["S0001"]["text"] == segments[0].text

    def test_format_transcript(self, synthetic_transcript_path):
        segments, _ = load_segments_from_transcript(synthetic_transcript_path)
        formatted = format_transcript_for_prompt(segments[:3])

        assert "[S0001 00:00:00.0–00:00:05.2]" in formatted
        assert "Good morning, everyone" in formatted
        assert "[S0002" in formatted

    def test_format_timestamp(self):
        assert format_timestamp(0.0) == "00:00:00.0"
        assert format_timestamp(65.8) == "00:01:05.8"
        assert format_timestamp(3661.5) == "01:01:01.5"


class TestContentLLMStageWithMockAPI:
    """Test content_llm stage with mocked LLM API"""

    @pytest.fixture
    def mock_llm_client(self):
        """Mock LLM client that returns valid schema-compliant responses"""
        with patch("pipeline.stages.content_llm.LLMClient") as MockClient:
            client_instance = MockClient.return_value

            # Mock reset_cost_tracking
            client_instance.reset_cost_tracking = MagicMock()
            client_instance.total_cost = 0.15
            client_instance.cost_ceiling = 0.50

            # Mock generate_structured to return valid responses
            def mock_generate_structured(prompt_id, inputs, schema, temperature=None):
                # Return schema-compliant mock data based on prompt_id
                if prompt_id == "outline_v1":
                    data = {
                        "sections": [
                            {
                                "title": "Introduction",
                                "start_seg": "S0001",
                                "end_seg": "S0004",
                                "purpose": "Set context and state the problem",
                            },
                            {
                                "title": "Three-Step Solution",
                                "start_seg": "S0005",
                                "end_seg": "S0016",
                                "purpose": "Describe the approach and results",
                            },
                            {
                                "title": "Call to Action",
                                "start_seg": "S0017",
                                "end_seg": "S0024",
                                "purpose": "Challenge audience and close",
                            },
                        ],
                        "main_points": 3,
                        "signposts": [
                            {"seg_id": "S0005", "quote": "First, we identified", "type": "preview"},
                            {"seg_id": "S0006", "quote": "Second, we stripped away", "type": "transition"},
                            {"seg_id": "S0007", "quote": "And finally, we tested", "type": "transition"},
                            {"seg_id": "S0017", "quote": "So to summarize", "type": "recap"},
                        ],
                        "recap_seg": "S0017",
                        "outline_clarity_level": 4.5,
                        "rationale": "Clear three-part structure with explicit signposts",
                        "insufficient_evidence": False,
                    }
                elif prompt_id == "message_v1":
                    data = {
                        "core_message": {
                            "text": "Simplicity creates value by removing friction",
                            "quote": "When you remove friction, you create value",
                            "seg_ids": ["S0010"],
                            "claim_type": "claim",
                            "level": 4.5,
                            "rationale": "Clear claim stated early and reinforced throughout",
                        },
                        "reinforcements": [
                            {"seg_id": "S0018", "quote": "Simplicity isn't about doing less"},
                        ],
                        "cta": {
                            "text": "Go back and ask what can we remove",
                            "seg_ids": ["S0019", "S0020"],
                            "specificity_level": 4.0,
                            "rationale": "Clear action with specific steps",
                        },
                        "bluf": {
                            "present": True,
                            "seg_id": "S0002",
                        },
                        "insufficient_evidence": False,
                    }
                elif prompt_id == "story_impact_v1":
                    data = {
                        "stories": [
                            {
                                "start_seg": "S0008",
                                "end_seg": "S0009",
                                "character": "Sarah, enterprise customer",
                                "conflict": "Spending 20 minutes per campaign",
                                "resolution": "New design reduced time to 2 minutes",
                                "point": "Simplicity reduces friction",
                                "tied_to_message": True,
                            }
                        ],
                        "contrasts": [
                            {"seg_id": "S0003", "quote": "Too many features vs doing one thing well"},
                        ],
                        "clt_instances": [
                            {
                                "type": "rhetorical_question",
                                "seg_id": "S0004",
                                "quote": "What if we focused on doing one thing really well?",
                            },
                            {
                                "type": "three_part_list",
                                "seg_id": "S0017",
                                "quote": "Focus. Remove. Test.",
                            },
                        ],
                        "success_profile": {
                            "simple_level": 5.0,
                            "unexpected_level": 3.5,
                            "concrete_level": 4.5,
                            "credible_level": 4.0,
                            "emotional_level": 3.5,
                            "stories_level": 4.0,
                            "rationale": "Strong concrete examples and data",
                        },
                        "memorable_moment": {
                            "seg_id": "S0012",
                            "quote": "3.2 to 4.7 out of 5",
                            "why_memorable": "Dramatic quantified improvement",
                        },
                        "insufficient_evidence": False,
                    }
                elif prompt_id == "audience_clarity_v1":
                    data = {
                        "jargon": [
                            {"term": "net promoter score", "first_seg": "S0013", "defined": False},
                        ],
                        "speaker_centric_phrases": [],
                        "claims": [
                            {
                                "seg_id": "S0011",
                                "claim": "Support tickets dropped by 60%",
                                "support_type": "data",
                            },
                        ],
                        "redundancy_spans": [],
                        "vagueness": [],
                        "audience_fit_level": 4.0,
                        "clarity_level": 4.5,
                        "rationale": "Clear language with strong data support",
                        "insufficient_evidence": False,
                    }
                elif prompt_id == "open_close_v1":
                    data = {
                        "opening": {
                            "hook_type": "question",
                            "hook_level": 4.0,
                            "value_preview_level": 4.5,
                            "throat_clearing_end_seg": None,
                            "rationale": "Sets problem and asks compelling question",
                        },
                        "closing": {
                            "ending_type": "cta",
                            "message_restated": True,
                            "cta_clear": True,
                            "fades_out": False,
                            "closing_level": 4.5,
                            "rationale": "Strong call to action with promise",
                        },
                        "insufficient_evidence": False,
                    }
                else:
                    data = {}

                return LLMResponse(
                    data=data,
                    usage=UsageStats(
                        prompt_tokens=1000,
                        completion_tokens=500,
                        total_tokens=1500,
                        cost_usd=0.03,
                        model="grok-beta",
                        provider="xai",
                    ),
                    raw_response={},
                    prompt_id=prompt_id,
                    prompt_version="1.0.0",
                )

            client_instance.generate_structured = mock_generate_structured

            yield client_instance

    def test_content_llm_stage_with_mock(
        self, synthetic_transcript_path, output_dir, mock_llm_client
    ):
        """Test full content_llm stage with mocked API"""
        from pipeline.stages.content_llm import content_llm_stage

        result = content_llm_stage(
            transcript_path=synthetic_transcript_path,
            output_dir=output_dir,
            session_id="test_session",
            context_type="keynote",
            language="en",
            max_duration_s=180.0,
        )

        # Check output structure
        assert result.outline is not None
        assert result.message is not None
        assert result.story_impact is not None
        assert result.audience_clarity is not None
        assert result.open_close is not None

        # Check outline
        assert len(result.outline["sections"]) == 3
        assert result.outline["main_points"] == 3
        assert result.outline["outline_clarity_level"] == 4.5

        # Check message
        assert result.message["core_message"]["claim_type"] == "claim"
        assert "friction" in result.message["core_message"]["quote"].lower()

        # Check story
        assert len(result.story_impact["stories"]) == 1
        assert result.story_impact["stories"][0]["tied_to_message"]

        # Check cost tracking
        assert result.total_cost_usd > 0

        # Check output file was written
        output_file = output_dir / "content.json"
        assert output_file.exists()

        with open(output_file) as f:
            saved_data = json.load(f)
            assert "outline" in saved_data
            assert "message" in saved_data


@pytest.mark.skipif(
    not os.getenv("LLM_API_KEY"),
    reason="LLM_API_KEY not set - skipping live API test",
)
class TestContentLLMLiveAPI:
    """Live API tests (only run when LLM_API_KEY is set)"""

    def test_live_outline_call(self, synthetic_transcript_path):
        """Test live API call for outline prompt (uses cassettes)"""
        from pipeline.stages.content_llm import (
            format_transcript_for_prompt,
            load_segments_from_transcript,
        )

        segments, segment_map = load_segments_from_transcript(synthetic_transcript_path)
        transcript = format_transcript_for_prompt(segments)

        client = LLMClient()

        schema_path = (
            Path(__file__).parent.parent / "llm" / "schemas" / "outline_v1.json"
        )
        with open(schema_path) as f:
            schema = json.load(f)

        response = client.generate_structured(
            prompt_id="outline_v1",
            inputs={
                "transcript": transcript,
                "context_type": "keynote",
                "language": "en",
            },
            schema=schema,
        )

        # Validate response structure
        assert "sections" in response.data
        assert "main_points" in response.data
        assert "outline_clarity_level" in response.data
        assert isinstance(response.data["outline_clarity_level"], (int, float))
        assert 1.0 <= response.data["outline_clarity_level"] <= 5.0

        # Check cost was tracked
        assert response.usage.cost_usd > 0
