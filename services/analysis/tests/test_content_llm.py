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


def test_down_model_writes_unavailable_content(tmp_path: Path):
    transcript = tmp_path / "transcript.json"
    transcript.write_text(
        json.dumps({"segments": [{"text": "Hello", "start": 0, "end": 1}]}),
        encoding="utf-8",
    )
    with patch(
        "pipeline.stages.content_llm.content_llm_stage",
        side_effect=ConnectionError("connection refused"),
    ):
        from pipeline.stages.content_llm import run_content_llm_safe

        outcome = run_content_llm_safe(
            transcript_path=transcript,
            output_dir=tmp_path,
            session_id="session",
        )
    assert outcome["status"] == "failed"
    payload = json.loads((tmp_path / "content.json").read_text())
    assert payload["unavailable"] is True
    assert "language model was unavailable" in payload["unavailable_reason"]
    assert payload["message"] is None


class _Clock:
    """Advances only while a model call is in flight."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def during_call(self, seconds: float) -> None:
        self.now += seconds


def _llm_response(prompt_id: str, data: dict) -> LLMResponse:
    return LLMResponse(
        data=data,
        usage=UsageStats(
            prompt_tokens=100,
            completion_tokens=40,
            total_tokens=140,
            cost_usd=0.0,
            model="qwen/qwen3.8-27b",
            provider="local",
        ),
        raw_response={},
        prompt_id=prompt_id,
        prompt_version="1.0.0",
    )


def _bind_client(mock_cls, generate):
    client = mock_cls.return_value
    client.reset_cost_tracking = MagicMock()
    client.total_cost = 0.0
    client.cost_ceiling = 0.50
    client.generate_structured = generate
    return client


def _minimal_payload(prompt_id: str, quote: str = "hello") -> dict:
    if prompt_id == "outline_v1":
        return {
            "sections": [
                {
                    "title": "Opening",
                    "start_seg": "S0001",
                    "end_seg": "S0001",
                    "purpose": "State the point",
                }
            ],
            "main_points": 1,
            "signposts": [{"seg_id": "S0001", "quote": quote, "type": "preview"}],
            "recap_seg": "S0001",
            "outline_clarity_level": 4.0,
            "rationale": "The slice is easy to follow and the speaker sounded happy.",
            "insufficient_evidence": False,
        }
    if prompt_id == "open_close_v1":
        return {
            "opening": {
                "hook_type": "statement",
                "hook_level": 3.0,
                "value_preview_level": 3.0,
                "throat_clearing_end_seg": None,
                "rationale": "States the point quickly",
            },
            "closing": {
                "ending_type": "cta",
                "message_restated": True,
                "cta_clear": True,
                "fades_out": False,
                "closing_level": 3.0,
                "rationale": "Restates the point",
            },
            "insufficient_evidence": False,
        }
    return {"insufficient_evidence": False}


def _write_transcript(path: Path, segments: list[dict], duration: float) -> None:
    path.write_text(
        json.dumps({"language": "en", "duration": duration, "segments": segments}),
        encoding="utf-8",
    )


def _long_segments() -> tuple[list[dict], str, float]:
    """Synthetic 60-minute talk. No recording, no personal voice."""
    sentence = "We remove friction and test the simpler path before the next step."
    segments = []
    t = 0.0
    for i in range(400):
        segments.append({"text": sentence, "start": t, "end": t + 9.0})
        t += 9.0
    return segments, sentence, t


def test_chunk_segments_splits_on_formatted_token_budget():
    from pipeline.stages.content_llm import (
        Segment,
        chunk_segments,
        estimate_tokens,
        format_transcript_for_prompt,
    )

    assert chunk_segments([]) == []
    text = "word " * 30
    segments = [
        Segment(seg_id=f"S{i + 1:04d}", text=text, start_time=float(i), end_time=float(i + 1))
        for i in range(40)
    ]
    chunks = chunk_segments(segments, max_tokens=180)
    assert len(chunks) > 1
    flat = [seg.seg_id for chunk in chunks for seg in chunk]
    assert flat == [seg.seg_id for seg in segments]
    for chunk in chunks:
        tokens = estimate_tokens(format_transcript_for_prompt(chunk))
        if len(chunk) > 1:
            assert tokens <= 180

    huge = Segment(seg_id="S0001", text="x" * 5000, start_time=0.0, end_time=1.0)
    alone = chunk_segments([huge], max_tokens=10)
    assert len(alone) == 1
    assert len(alone[0]) == 1


def test_long_session_threshold_is_strict():
    from pipeline.stages.content_llm import (
        LONG_SESSION_DURATION_S,
        LONG_SESSION_TOKEN_THRESHOLD,
        Segment,
        consistency_k,
        is_long_session,
        resolve_talk_duration_s,
    )

    assert is_long_session(100, LONG_SESSION_DURATION_S) is False
    assert is_long_session(100, LONG_SESSION_DURATION_S + 0.1) is True
    assert is_long_session(LONG_SESSION_TOKEN_THRESHOLD, 60) is False
    assert is_long_session(LONG_SESSION_TOKEN_THRESHOLD + 1, 60) is True
    assert consistency_k(False) == 3
    assert consistency_k(True) == 1

    segments = [Segment("S0001", "Hello", 0.0, 42.0)]
    assert resolve_talk_duration_s(segments, None, 5400.0) == 42.0
    assert resolve_talk_duration_s(segments, 90.0, 5400.0) == 90.0
    assert resolve_talk_duration_s(segments, None, 180.0) == 180.0


def test_guard_refuses_multiline_transcript_over_cap():
    from pipeline.stages.content_llm import _guard_transcript_payload

    huge = "\n".join(["hello world from the talk"] * 2000)
    with pytest.raises(ValueError, match="whole-transcript"):
        _guard_transcript_payload({"transcript": huge}, huge)


def test_short_session_keeps_k3_and_one_chunk(synthetic_transcript_path, tmp_path):
    from pipeline.stages.content_llm import estimate_tokens, format_transcript_for_prompt, load_segments_from_transcript, run_content_llm_safe

    segments, _ = load_segments_from_transcript(synthetic_transcript_path)
    full = format_transcript_for_prompt(segments)
    assert estimate_tokens(full) <= 6000
    calls = []

    def generate(prompt_id, inputs, schema, temperature=None):
        calls.append({"prompt_id": prompt_id, "inputs": inputs, "temperature": temperature})
        return _llm_response(prompt_id, _minimal_payload(prompt_id, "Good morning, everyone."))

    progress = []
    ready = []
    with patch("pipeline.stages.content_llm.LLMClient") as mock_cls:
        _bind_client(mock_cls, generate)
        outcome = run_content_llm_safe(
            transcript_path=synthetic_transcript_path,
            output_dir=tmp_path,
            session_id="short",
            max_duration_s=180.0,
            duration_s=180.0,
            budget_s=480,
            on_progress=lambda message, pct: progress.append((message, pct)),
            on_partial_ready=ready.append,
        )

    assert outcome["status"] == "succeeded"
    assert outcome["partial"] is False
    assert outcome["k"] == 3
    assert outcome["chunk_count"] == 1
    assert outcome["message"] == "Content scores ready"
    assert len(calls) == 15
    assert [call["temperature"] for call in calls] == [0.3, 0.4, 0.5] * 5
    assert all("chunk_analyses" not in call["inputs"] for call in calls)
    assert all("instruction" not in call["inputs"] for call in calls)
    assert progress[0][0] == "outline 1/1"
    assert all(87.0 < pct <= 87.99 for _, pct in progress)
    assert ready == [["structure"]]
    saved = json.loads((tmp_path / "content.json").read_text())
    assert saved["provenance"]["k"] == 3
    assert saved["provenance"]["chunk_count"] == 1
    assert saved["provenance"]["long_session"] is False
    assert "unavailable" not in saved


def test_long_synthetic_transcript_map_reduces_under_token_cap(tmp_path):
    from pipeline.stages.content_llm import (
        CALL_TOKEN_CAP,
        estimate_tokens,
        run_content_llm_safe,
    )

    segments, sentence, duration = _long_segments()
    path = tmp_path / "transcript.json"
    _write_transcript(path, segments, duration)
    assert duration > 12 * 60
    calls = []

    def generate(prompt_id, inputs, schema, temperature=None):
        calls.append(
            {
                "prompt_id": prompt_id,
                "inputs": json.loads(json.dumps(inputs)),
                "temperature": temperature,
            }
        )
        return _llm_response(prompt_id, _minimal_payload(prompt_id, sentence))

    progress = []
    ready = []
    with patch("pipeline.stages.content_llm.LLMClient") as mock_cls:
        _bind_client(mock_cls, generate)
        outcome = run_content_llm_safe(
            transcript_path=path,
            output_dir=tmp_path,
            session_id="long",
            duration_s=duration,
            max_duration_s=duration,
            on_progress=lambda message, pct: progress.append(message),
            on_partial_ready=ready.append,
        )

    saved = json.loads((tmp_path / "content.json").read_text())
    chunk_count = saved["provenance"]["chunk_count"]
    outline_count = saved["provenance"]["outline_chunk_count"]
    assert chunk_count >= 2
    assert outline_count > chunk_count
    assert saved["provenance"]["outline_chunk_tokens"] == 2500
    assert saved["provenance"]["k"] == 1
    assert saved["provenance"]["long_session"] is True
    assert saved["provenance"]["estimated_tokens"] > CALL_TOKEN_CAP
    assert outcome["status"] == "succeeded"
    assert outcome["partial"] is False
    assert saved["provenance"]["elapsed_s"] < saved["provenance"]["budget_s"]
    assert len(calls) == (outline_count + 1) + 3 * (chunk_count + 1) + 1
    assert {call["temperature"] for call in calls} == {0.3}

    for call in calls:
        inputs = call["inputs"]
        for key in ("transcript", "opening_transcript", "closing_transcript"):
            text = inputs.get(key)
            if not isinstance(text, str):
                continue
            assert estimate_tokens(text) <= CALL_TOKEN_CAP
            assert text.count("We remove friction") < 400
        if "chunk_analyses" in inputs:
            assert "transcript" not in inputs
            assert inputs["instruction"].startswith("Merge")
    assert any("chunk_analyses" in call["inputs"] for call in calls)
    assert f"outline 1/{outline_count}" in progress
    assert "outline reduce" in progress
    assert "message 2/" + str(chunk_count) in progress or f"message {chunk_count}/{chunk_count}" in progress
    assert ready == [["structure"]]
    assert "verification_metadata" in saved["outline"]
    warnings = saved["outline"].get("emotion_warnings") or []
    assert any("happy" in term for item in warnings for term in item.get("terms") or [])
    assert saved["outline"]["signposts"][0]["quote"] == sentence


def test_budget_finishes_current_call_then_keeps_partial_prompt(synthetic_transcript_path, tmp_path):
    from pipeline.stages.content_llm import content_progress_view, run_content_llm_safe

    clock = _Clock()
    calls = []

    def generate(prompt_id, inputs, schema, temperature=None):
        clock.during_call(90)
        calls.append(prompt_id)
        return _llm_response(prompt_id, _minimal_payload(prompt_id, "Good morning, everyone."))

    with patch("pipeline.stages.content_llm.LLMClient") as mock_cls:
        _bind_client(mock_cls, generate)
        outcome = run_content_llm_safe(
            transcript_path=synthetic_transcript_path,
            output_dir=tmp_path,
            session_id="budget-one",
            duration_s=13 * 60,
            max_duration_s=13 * 60,
            budget_s=60,
            clock=clock,
        )

    saved = json.loads((tmp_path / "content.json").read_text())
    assert calls == ["outline_v1"]
    assert saved["outline"] is not None
    assert saved["message"] is None
    assert saved["story_impact"] is None
    assert saved["open_close"] is None
    assert saved["provenance"]["k"] == 1
    assert saved["provenance"]["chunk_count"] == 1
    assert saved["provenance"]["partial"] is True
    assert saved["provenance"]["stop_reason"] == "budget"
    assert saved["provenance"]["completed_prompts"] == ["outline_v1"]
    assert "message_v1" in saved["provenance"]["unfinished_prompts"]
    assert "unavailable" not in saved
    assert outcome["status"] == "succeeded"
    assert outcome["partial"] is True
    assert "1-minute budget after outline" in outcome["message"]
    assert "N/A" in outcome["message"]
    view = content_progress_view(outcome)
    assert view["step_status"] == "succeeded"
    assert view["progress_status"] == "succeeded"
    assert "1-minute budget" in view["message"]


def test_budget_stops_between_chunks_and_persists_them(tmp_path):
    from pipeline.stages.content_llm import CALL_TOKEN_CAP, estimate_tokens, run_content_llm_safe

    segments, sentence, duration = _long_segments()
    path = tmp_path / "transcript.json"
    _write_transcript(path, segments, duration)
    clock = _Clock()
    calls = []

    def generate(prompt_id, inputs, schema, temperature=None):
        clock.during_call(100)
        transcript = inputs.get("transcript")
        if isinstance(transcript, str):
            assert estimate_tokens(transcript) <= CALL_TOKEN_CAP
        calls.append(prompt_id)
        return _llm_response(prompt_id, _minimal_payload(prompt_id, sentence))

    with patch("pipeline.stages.content_llm.LLMClient") as mock_cls:
        _bind_client(mock_cls, generate)
        outcome = run_content_llm_safe(
            transcript_path=path,
            output_dir=tmp_path,
            session_id="budget-chunk",
            duration_s=duration,
            max_duration_s=duration,
            budget_s=50,
            clock=clock,
        )

    saved = json.loads((tmp_path / "content.json").read_text())
    assert calls == ["outline_v1"]
    assert saved["outline"] is None
    chunk = saved["provenance"]["chunks"]["outline_v1"]
    assert chunk["mapped"] == 1
    assert chunk["reduced"] is False
    assert chunk["total"] >= 2
    assert len(chunk["pending"]) == 1
    assert outcome["status"] == "succeeded"
    assert outcome["partial"] is True
    assert saved["provenance"]["completed_prompts"] == []


def test_zero_budget_stops_before_any_call(synthetic_transcript_path, tmp_path, monkeypatch):
    from pipeline.stages.content_llm import run_content_llm_safe

    calls = []

    def generate(prompt_id, inputs, schema, temperature=None):
        calls.append(prompt_id)
        return _llm_response(prompt_id, {"insufficient_evidence": True})

    monkeypatch.setenv("CONTENT_LLM_BUDGET_S", "0")
    with patch("pipeline.stages.content_llm.LLMClient") as mock_cls:
        _bind_client(mock_cls, generate)
        outcome = run_content_llm_safe(
            transcript_path=synthetic_transcript_path,
            output_dir=tmp_path,
            session_id="budget-zero",
            duration_s=30,
            max_duration_s=30,
        )
    assert calls == []
    saved = json.loads((tmp_path / "content.json").read_text())
    assert saved["outline"] is None
    assert saved.get("unavailable") is not True
    assert outcome["status"] == "succeeded"
    assert outcome["partial"] is True
    assert "before any prompt finished" in outcome["message"]

    calls.clear()
    with patch("pipeline.stages.content_llm.LLMClient") as mock_cls:
        _bind_client(mock_cls, generate)
        outcome = run_content_llm_safe(
            transcript_path=synthetic_transcript_path,
            output_dir=tmp_path,
            session_id="budget-override",
            duration_s=30,
            max_duration_s=30,
            budget_s=600,
        )
    assert len(calls) == 15
    assert outcome["partial"] is False


def test_model_error_on_first_prompt_stays_unavailable(synthetic_transcript_path, tmp_path):
    from pipeline.stages.content_llm import run_content_llm_safe

    def generate(prompt_id, inputs, schema, temperature=None):
        raise ConnectionError("connection refused")

    with patch("pipeline.stages.content_llm.LLMClient") as mock_cls:
        _bind_client(mock_cls, generate)
        outcome = run_content_llm_safe(
            transcript_path=synthetic_transcript_path,
            output_dir=tmp_path,
            session_id="down",
            duration_s=30,
            max_duration_s=30,
        )
    assert outcome["status"] == "failed"
    saved = json.loads((tmp_path / "content.json").read_text())
    assert saved["unavailable"] is True


def test_model_error_after_a_prompt_keeps_partial_content(synthetic_transcript_path, tmp_path):
    from pipeline.stages.content_llm import run_content_llm_safe

    def generate(prompt_id, inputs, schema, temperature=None):
        if prompt_id == "message_v1":
            raise ConnectionError("connection refused")
        return _llm_response(prompt_id, _minimal_payload(prompt_id, "Good morning, everyone."))

    with patch("pipeline.stages.content_llm.LLMClient") as mock_cls:
        _bind_client(mock_cls, generate)
        outcome = run_content_llm_safe(
            transcript_path=synthetic_transcript_path,
            output_dir=tmp_path,
            session_id="partial-error",
            duration_s=30,
            max_duration_s=30,
            budget_s=600,
        )
    saved = json.loads((tmp_path / "content.json").read_text())
    assert outcome["status"] == "succeeded"
    assert outcome["partial"] is True
    assert "language model failed" in outcome["message"]
    assert saved["outline"] is not None
    assert saved["message"] is None
    assert saved.get("unavailable") is not True
    assert saved["provenance"]["stop_reason"] == "error"


def test_timeout_retries_once_then_finishes(synthetic_transcript_path, tmp_path):
    from llm.exceptions import LLMTimeoutError
    from pipeline.stages.content_llm import run_content_llm_safe

    calls = []

    def generate(prompt_id, inputs, schema, temperature=None):
        calls.append(prompt_id)
        if prompt_id == "outline_v1" and calls.count("outline_v1") == 1:
            raise LLMTimeoutError("slow chunk")
        return _llm_response(prompt_id, _minimal_payload(prompt_id, "Good morning, everyone."))

    with patch("pipeline.stages.content_llm.LLMClient") as mock_cls:
        _bind_client(mock_cls, generate)
        outcome = run_content_llm_safe(
            transcript_path=synthetic_transcript_path,
            output_dir=tmp_path,
            session_id="retry-once",
            duration_s=13 * 60,
            max_duration_s=13 * 60,
            budget_s=480,
        )

    saved = json.loads((tmp_path / "content.json").read_text())
    assert calls.count("outline_v1") == 2
    assert outcome["status"] == "succeeded"
    assert outcome["partial"] is False
    assert saved["outline"] is not None
    assert saved.get("unavailable") is not True


def test_one_prompt_timeout_does_not_drop_the_model(synthetic_transcript_path, tmp_path):
    from llm.exceptions import LLMTimeoutError
    from pipeline.stages.content_llm import run_content_llm_safe

    def generate(prompt_id, inputs, schema, temperature=None):
        if prompt_id == "outline_v1":
            raise LLMTimeoutError("slow chunk")
        return _llm_response(prompt_id, _minimal_payload(prompt_id, "Good morning, everyone."))

    with patch("pipeline.stages.content_llm.LLMClient") as mock_cls:
        _bind_client(mock_cls, generate)
        outcome = run_content_llm_safe(
            transcript_path=synthetic_transcript_path,
            output_dir=tmp_path,
            session_id="degrade-one",
            duration_s=13 * 60,
            max_duration_s=13 * 60,
            budget_s=480,
        )

    saved = json.loads((tmp_path / "content.json").read_text())
    assert outcome["status"] == "succeeded"
    assert outcome["partial"] is True
    assert "didn't finish" in outcome["message"]
    assert saved.get("unavailable") is not True
    assert saved["outline"] is None
    assert saved["message"] is not None
    assert "outline_v1" in saved["provenance"]["degraded_prompts"]
    assert saved["provenance"]["stop_reason"] == "timeout"


def test_budget_and_read_timeout_scale(monkeypatch):
    from pipeline.stages.content_llm import resolve_content_budget_s, resolve_read_timeout_s

    monkeypatch.delenv("CONTENT_LLM_BUDGET_S", raising=False)
    monkeypatch.delenv("CONTENT_LLM_TIMEOUT_S", raising=False)
    assert resolve_content_budget_s(60, 20000) == 60
    assert resolve_content_budget_s(None, 6000) == 480
    assert resolve_content_budget_s(None, 14000) == 660
    assert resolve_read_timeout_s(2500) == 180
    assert resolve_read_timeout_s(5000) == 360
    assert resolve_read_timeout_s(20000) == 600
    monkeypatch.setenv("CONTENT_LLM_TIMEOUT_S", "90")
    assert resolve_read_timeout_s(2500) == 90
    monkeypatch.setenv("CONTENT_LLM_BUDGET_S", "0")
    assert resolve_content_budget_s(None, 20000) == 0
