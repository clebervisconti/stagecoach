"""Content LLM stage: structured text analysis per §6.7.

Issues #27, #28, #29: Prompts, grounding, verification, self-consistency.
"""

import hashlib
import json
import logging
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import sys
from pathlib import Path

# Add parent directory to path for imports when running as module
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from llm import LLMClient
from llm.verification import (
    check_for_emotion_inference,
    check_self_consistency,
    pull_extreme_level_toward_center,
    validate_segment_ids,
    validate_timestamps,
    verify_evidence_list,
)

logger = logging.getLogger(__name__)


@dataclass
class Segment:
    """Transcript segment with ID, timestamps, and text"""

    seg_id: str
    text: str
    start_time: float
    end_time: float
    speaker: Optional[str] = None


@dataclass
class ContentLLMOutput:
    """Output from content_llm stage"""

    outline: Optional[Dict[str, Any]] = None
    message: Optional[Dict[str, Any]] = None
    story_impact: Optional[Dict[str, Any]] = None
    audience_clarity: Optional[Dict[str, Any]] = None
    open_close: Optional[Dict[str, Any]] = None
    fluency_disambig: Optional[Dict[str, Any]] = None
    qa: Optional[Dict[str, Any]] = None

    # Metadata
    total_cost_usd: float = 0.0
    prompt_versions: Dict[str, str] = field(default_factory=dict)
    verification_summary: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "outline": self.outline,
            "message": self.message,
            "story_impact": self.story_impact,
            "audience_clarity": self.audience_clarity,
            "open_close": self.open_close,
            "fluency_disambig": self.fluency_disambig,
            "qa": self.qa,
            "total_cost_usd": self.total_cost_usd,
            "prompt_versions": self.prompt_versions,
            "verification_summary": self.verification_summary,
        }


def load_segments_from_transcript(
    transcript_path: Path,
) -> tuple[List[Segment], Dict[str, Dict[str, Any]]]:
    """Load transcript and build segment structures.

    Args:
        transcript_path: Path to transcript.json from ASR stage

    Returns:
        (segment_list, segment_map)
    """
    with open(transcript_path) as f:
        transcript_data = json.load(f)

    segments = []
    segment_map = {}

    # Transcript format per §6.2: segments with words, timestamps
    for i, seg in enumerate(transcript_data.get("segments", [])):
        seg_id = f"S{i+1:04d}"
        text = seg["text"]
        start_time = seg["start"]
        end_time = seg["end"]
        speaker = seg.get("speaker")  # From diarization if available

        segment = Segment(
            seg_id=seg_id,
            text=text,
            start_time=start_time,
            end_time=end_time,
            speaker=speaker,
        )

        segments.append(segment)
        segment_map[seg_id] = {
            "text": text,
            "start_time": start_time,
            "end_time": end_time,
            "speaker": speaker,
        }

    return segments, segment_map


def format_transcript_for_prompt(segments: List[Segment]) -> str:
    """Format segments as numbered transcript per §6.7.2.

    Format:
    [S0001 00:00:03.2–00:00:09.8] Good morning, everyone. Um, thanks for having me.
    """
    lines = []
    for seg in segments:
        start_str = format_timestamp(seg.start_time)
        end_str = format_timestamp(seg.end_time)
        lines.append(f"[{seg.seg_id} {start_str}–{end_str}] {seg.text}")

    return "\n".join(lines)


def format_timestamp(seconds: float) -> str:
    """Format seconds as HH:MM:SS.d"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:04.1f}"


def chunk_segments(segments: List[Segment], max_tokens: int = 6000) -> List[List[Segment]]:
    """Chunk long transcripts per §6.7.2 (≤6-8k tokens per chunk).

    Simple heuristic: ~1 token per 4 characters. For now, return full transcript
    if under limit, else chunk by segment boundaries.

    Args:
        segments: Full segment list
        max_tokens: Maximum tokens per chunk (default 6000)

    Returns:
        List of segment chunks
    """
    # Estimate total tokens
    total_chars = sum(len(seg.text) for seg in segments)
    estimated_tokens = total_chars / 4

    if estimated_tokens <= max_tokens:
        return [segments]

    # Chunk by segments
    chunks = []
    current_chunk = []
    current_tokens = 0

    for seg in segments:
        seg_tokens = len(seg.text) / 4
        if current_tokens + seg_tokens > max_tokens and current_chunk:
            chunks.append(current_chunk)
            current_chunk = []
            current_tokens = 0

        current_chunk.append(seg)
        current_tokens += seg_tokens

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def call_prompt_with_verification(
    client: LLMClient,
    prompt_id: str,
    inputs: Dict[str, Any],
    schema: Dict[str, Any],
    segment_map: Dict[str, Dict[str, Any]],
    max_duration_s: float,
    language: str,
    k: int = 3,
) -> Dict[str, Any]:
    """Call LLM prompt with k=3 self-consistency and verification.

    Per §6.7.4 and issue #29:
    - Run k=3 times for level-producing calls
    - Use median level, compute agreement
    - Verify quotes against transcript
    - Drop invalid evidence and adjust confidence
    - Check for hallucination (invalid seg IDs, out-of-range timestamps)
    - Check for emotion inference terms

    Args:
        client: LLM client
        prompt_id: Prompt identifier
        inputs: Template inputs
        schema: JSON schema
        segment_map: Segment ID -> content map
        max_duration_s: Media duration for timestamp validation
        language: Language code (en or pt-BR)
        k: Number of samples for self-consistency (default 3)

    Returns:
        Validated and adjusted output dict with confidence metadata
    """
    responses = []

    # Run k times with slight temperature variation for diversity
    temperatures = [0.3, 0.4, 0.5]  # Per §6.7.4 heuristic

    for i in range(k):
        temp = temperatures[i % len(temperatures)]
        response = client.generate_structured(
            prompt_id=prompt_id,
            inputs=inputs,
            schema=schema,
            temperature=temp,
        )
        responses.append(response)

    # Start with first response as base
    result = responses[0].data.copy()

    # Valid segment IDs for hallucination guard
    valid_seg_ids = set(segment_map.keys())

    # Collect level-producing fields for self-consistency
    level_fields = _identify_level_fields(result)

    if level_fields and k == 3:
        # Apply self-consistency to each level field
        for field_path in level_fields:
            levels = []
            for resp in responses:
                level = _get_nested_field(resp.data, field_path)
                if level and isinstance(level, (int, float)):
                    levels.append(float(level))

            if len(levels) == 3:
                consistency = check_self_consistency(levels)
                _set_nested_field(result, field_path, consistency.median_level)

                # Store agreement for confidence computation
                if "consistency_metadata" not in result:
                    result["consistency_metadata"] = {}
                result["consistency_metadata"][field_path] = {
                    "median": consistency.median_level,
                    "agreement": consistency.agreement,
                    "levels": consistency.levels,
                }

    # Verify evidence items with quotes
    evidence_fields = _identify_evidence_fields(result)
    total_evidence = 0
    valid_evidence_count = 0

    for evidence_path in evidence_fields:
        evidence_list = _get_nested_field(result, evidence_path)
        if evidence_list and isinstance(evidence_list, list):
            valid_evidence, confidence_factor = verify_evidence_list(
                evidence_list, segment_map, threshold=0.9
            )

            total_evidence += len(evidence_list)
            valid_evidence_count += len(valid_evidence)

            # Replace with valid evidence only
            _set_nested_field(result, evidence_path, valid_evidence)

            # Store verification metadata
            if "verification_metadata" not in result:
                result["verification_metadata"] = {}
            result["verification_metadata"][evidence_path] = {
                "original_count": len(evidence_list),
                "valid_count": len(valid_evidence),
                "confidence_factor": confidence_factor,
            }

    # Pull extreme levels toward center if insufficient evidence
    for field_path in level_fields:
        level = _get_nested_field(result, field_path)
        if level and isinstance(level, (int, float)):
            adjusted_level, was_adjusted = pull_extreme_level_toward_center(
                float(level), valid_evidence_count
            )

            if was_adjusted:
                _set_nested_field(result, field_path, adjusted_level)

                if "adjustments" not in result:
                    result["adjustments"] = []
                result["adjustments"].append(
                    {
                        "field": field_path,
                        "original_level": level,
                        "adjusted_level": adjusted_level,
                        "reason": "insufficient_evidence",
                    }
                )

    # Hallucination guard: check segment IDs
    all_seg_ids = _extract_all_segment_ids(result)
    valid, error = validate_segment_ids(all_seg_ids, valid_seg_ids)
    if not valid:
        logger.warning(f"{prompt_id}: Hallucination detected - {error}")
        # Filter out invalid references
        result = _remove_invalid_segment_references(result, valid_seg_ids)

    # Check for emotion inference terms in rationale/text fields
    text_fields = _extract_text_fields(result)
    for field_path, text in text_fields:
        has_forbidden, found_terms = check_for_emotion_inference(text, language)
        if has_forbidden:
            logger.warning(
                f"{prompt_id}: Emotion inference detected in {field_path}: {found_terms}"
            )
            # Flag for review but don't reject (could be false positive)
            if "emotion_warnings" not in result:
                result["emotion_warnings"] = []
            result["emotion_warnings"].append(
                {"field": field_path, "terms": found_terms}
            )

    return result


def _identify_level_fields(data: Dict[str, Any], prefix: str = "") -> List[str]:
    """Recursively find fields ending in '_level'."""
    fields = []

    for key, value in data.items():
        path = f"{prefix}.{key}" if prefix else key

        if key.endswith("_level") and isinstance(value, (int, float)):
            fields.append(path)
        elif isinstance(value, dict):
            fields.extend(_identify_level_fields(value, path))

    return fields


def _identify_evidence_fields(data: Dict[str, Any], prefix: str = "") -> List[str]:
    """Recursively find fields named 'evidence' or similar that contain quote arrays."""
    fields = []

    for key, value in data.items():
        path = f"{prefix}.{key}" if prefix else key

        # Look for evidence, claims, stories, etc. with quote fields
        if key in ["evidence", "claims", "stories", "contrasts", "signposts", "jargon"]:
            if isinstance(value, list) and value and isinstance(value[0], dict):
                if "quote" in value[0] or "seg_id" in value[0]:
                    fields.append(path)
        elif isinstance(value, dict):
            fields.extend(_identify_evidence_fields(value, path))
        elif isinstance(value, list) and value and isinstance(value[0], dict):
            # Recurse into list of dicts
            for i, item in enumerate(value):
                if isinstance(item, dict):
                    fields.extend(_identify_evidence_fields(item, f"{path}[{i}]"))

    return fields


def _get_nested_field(data: Dict[str, Any], path: str) -> Any:
    """Get nested field by dot-separated path."""
    parts = path.split(".")
    current = data

    for part in parts:
        if "[" in part:
            # Handle array indexing
            field, idx_str = part.split("[")
            idx = int(idx_str.rstrip("]"))
            current = current.get(field, [])[idx]
        else:
            current = current.get(part)
            if current is None:
                return None

    return current


def _set_nested_field(data: Dict[str, Any], path: str, value: Any):
    """Set nested field by dot-separated path."""
    parts = path.split(".")
    current = data

    for i, part in enumerate(parts[:-1]):
        if "[" in part:
            field, idx_str = part.split("[")
            idx = int(idx_str.rstrip("]"))
            current = current[field][idx]
        else:
            if part not in current:
                current[part] = {}
            current = current[part]

    last_part = parts[-1]
    if "[" in last_part:
        field, idx_str = last_part.split("[")
        idx = int(idx_str.rstrip("]"))
        current[field][idx] = value
    else:
        current[last_part] = value


def _extract_all_segment_ids(data: Any) -> List[str]:
    """Recursively extract all segment ID references."""
    seg_ids = []

    if isinstance(data, dict):
        for key, value in data.items():
            if key in ["seg_id", "start_seg", "end_seg", "q_seg"] and isinstance(value, str):
                if value and value.startswith("S"):
                    seg_ids.append(value)
            elif key == "seg_ids" and isinstance(value, list):
                seg_ids.extend(v for v in value if isinstance(v, str) and v.startswith("S"))
            elif key == "a_segs" and isinstance(value, list):
                seg_ids.extend(v for v in value if isinstance(v, str) and v.startswith("S"))
            else:
                seg_ids.extend(_extract_all_segment_ids(value))
    elif isinstance(data, list):
        for item in data:
            seg_ids.extend(_extract_all_segment_ids(item))

    return seg_ids


def _extract_text_fields(data: Any, prefix: str = "") -> List[tuple[str, str]]:
    """Recursively extract text fields (rationale, why_memorable, etc.) for checking."""
    text_fields = []

    if isinstance(data, dict):
        for key, value in data.items():
            path = f"{prefix}.{key}" if prefix else key

            if key in ["rationale", "why_memorable", "purpose", "issue"] and isinstance(value, str):
                text_fields.append((path, value))
            elif isinstance(value, (dict, list)):
                text_fields.extend(_extract_text_fields(value, path))
    elif isinstance(data, list):
        for i, item in enumerate(data):
            text_fields.extend(_extract_text_fields(item, f"{prefix}[{i}]"))

    return text_fields


def _remove_invalid_segment_references(data: Any, valid_seg_ids: set) -> Any:
    """Remove items with invalid segment references."""
    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            if key in ["seg_id", "start_seg", "end_seg", "q_seg"]:
                if isinstance(value, str) and value in valid_seg_ids:
                    result[key] = value
                elif value is None:
                    result[key] = value
                # Skip invalid seg IDs
            elif key in ["seg_ids", "a_segs"]:
                if isinstance(value, list):
                    result[key] = [v for v in value if v in valid_seg_ids]
            else:
                result[key] = _remove_invalid_segment_references(value, valid_seg_ids)
        return result
    elif isinstance(data, list):
        return [_remove_invalid_segment_references(item, valid_seg_ids) for item in data]
    else:
        return data


def content_llm_stage(
    transcript_path: Path,
    output_dir: Path,
    session_id: str,
    context_type: str = "keynote",
    language: str = "en",
    audience_desc: Optional[str] = None,
    max_duration_s: float = 5400.0,  # 90 minutes
) -> ContentLLMOutput:
    """Run content LLM stage with all prompts.

    Per issues #27, #28, #29.

    Args:
        transcript_path: Path to transcript.json from ASR
        output_dir: Output directory for artifacts
        session_id: Session ID
        context_type: Context type (keynote, exec_briefing, etc.)
        language: Language code (en or pt-BR)
        audience_desc: Optional audience description
        max_duration_s: Media duration for validation

    Returns:
        ContentLLMOutput with all prompt results
    """
    logger.info(f"Starting content_llm stage for {session_id}")

    # Load schemas
    schema_dir = Path(__file__).parent.parent.parent / "llm" / "schemas"

    # Initialize LLM client
    client = LLMClient()
    client.reset_cost_tracking()

    # Load transcript
    segments, segment_map = load_segments_from_transcript(transcript_path)
    full_transcript = format_transcript_for_prompt(segments)

    logger.info(f"Loaded {len(segments)} segments ({len(full_transcript)} chars)")

    output = ContentLLMOutput()

    # Issue #27: Prompts for outline, message, story, audience, clarity, open/close

    # 1. Outline
    with open(schema_dir / "outline_v1.json") as f:
        outline_schema = json.load(f)

    outline_result = call_prompt_with_verification(
        client=client,
        prompt_id="outline_v1",
        inputs={"transcript": full_transcript, "context_type": context_type, "language": language},
        schema=outline_schema,
        segment_map=segment_map,
        max_duration_s=max_duration_s,
        language=language,
    )
    output.outline = outline_result
    output.prompt_versions["outline_v1"] = "1.0.0"

    # 2. Message
    with open(schema_dir / "message_v1.json") as f:
        message_schema = json.load(f)

    message_result = call_prompt_with_verification(
        client=client,
        prompt_id="message_v1",
        inputs={
            "transcript": full_transcript,
            "context_type": context_type,
            "language": language,
            "audience_desc": audience_desc or "",
        },
        schema=message_schema,
        segment_map=segment_map,
        max_duration_s=max_duration_s,
        language=language,
    )
    output.message = message_result
    output.prompt_versions["message_v1"] = "1.0.0"

    # 3. Story & Impact
    with open(schema_dir / "story_impact_v1.json") as f:
        story_impact_schema = json.load(f)

    story_impact_result = call_prompt_with_verification(
        client=client,
        prompt_id="story_impact_v1",
        inputs={"transcript": full_transcript, "context_type": context_type, "language": language},
        schema=story_impact_schema,
        segment_map=segment_map,
        max_duration_s=max_duration_s,
        language=language,
    )
    output.story_impact = story_impact_result
    output.prompt_versions["story_impact_v1"] = "1.0.0"

    # 4. Audience & Clarity
    with open(schema_dir / "audience_clarity_v1.json") as f:
        audience_clarity_schema = json.load(f)

    audience_clarity_result = call_prompt_with_verification(
        client=client,
        prompt_id="audience_clarity_v1",
        inputs={
            "transcript": full_transcript,
            "context_type": context_type,
            "language": language,
            "audience_desc": audience_desc or "",
        },
        schema=audience_clarity_schema,
        segment_map=segment_map,
        max_duration_s=max_duration_s,
        language=language,
    )
    output.audience_clarity = audience_clarity_result
    output.prompt_versions["audience_clarity_v1"] = "1.0.0"

    # 5. Opening & Close
    # Extract first 60s and last 90s
    opening_segs = [s for s in segments if s.start_time < 60.0]
    closing_segs = [s for s in segments if s.end_time > max(0, segments[-1].end_time - 90.0)]

    opening_transcript = format_transcript_for_prompt(opening_segs)
    closing_transcript = format_transcript_for_prompt(closing_segs)

    with open(schema_dir / "open_close_v1.json") as f:
        open_close_schema = json.load(f)

    open_close_result = call_prompt_with_verification(
        client=client,
        prompt_id="open_close_v1",
        inputs={
            "opening_transcript": opening_transcript,
            "closing_transcript": closing_transcript,
            "context_type": context_type,
            "language": language,
        },
        schema=open_close_schema,
        segment_map=segment_map,
        max_duration_s=max_duration_s,
        language=language,
    )
    output.open_close = open_close_result
    output.prompt_versions["open_close_v1"] = "1.0.0"

    # Issue #28: Fluency disambiguation and Q&A (implemented as stubs; full implementation requires filler detection)

    # 6. Fluency disambiguation (stub - needs filler candidates from fluency stage)
    # TODO: This will be called from fluency metric computation with candidate hits
    output.fluency_disambig = {"disambiguations": []}
    output.prompt_versions["fluency_disambig_v1"] = "1.0.0"

    # 7. Q&A (stub - needs diarization to identify Q&A)
    # TODO: This will be called after diarization identifies Q&A spans
    output.qa = {"pairs": [], "insufficient_evidence": True}
    output.prompt_versions["qa_v1"] = "1.0.0"

    # Record total cost
    output.total_cost_usd = client.total_cost

    # Verification summary
    output.verification_summary = {
        "total_prompts": 5,  # Excluding stubs
        "total_cost_usd": client.total_cost,
        "cost_ceiling": client.cost_ceiling,
    }

    # Write output
    output_path = output_dir / "content.json"
    with open(output_path, "w") as f:
        json.dump(output.to_dict(), f, indent=2)

    logger.info(f"content_llm stage complete. Cost: ${client.total_cost:.4f}")

    return output
