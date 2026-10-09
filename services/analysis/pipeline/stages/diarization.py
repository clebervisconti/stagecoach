"""Diarization stage: pyannote speaker diarization (gated on HF_TOKEN).

Per SPEC §6.3, §6.9, §4.4.17 and issue #22:
- pyannote speaker-diarization-community-1 (CC-BY-4.0, gated)
- Feature-gated on HF_TOKEN environment variable
- Without token: skip diarization, use LLM fallback for Q&A detection
- With token: full speaker segmentation, identify primary speaker
- Attribution per CC-BY-4.0 recorded in model registry
"""

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Check if diarization is enabled
HF_TOKEN = os.getenv("HF_TOKEN")
DIARIZATION_ENABLED = HF_TOKEN is not None

if DIARIZATION_ENABLED:
    try:
        from pyannote.audio import Pipeline
        logger.info("Diarization enabled: pyannote.audio loaded")
    except ImportError:
        logger.warning("HF_TOKEN set but pyannote.audio not installed")
        DIARIZATION_ENABLED = False
else:
    logger.info("Diarization disabled: HF_TOKEN not set")


@dataclass
class SpeakerSegment:
    """Speaker diarization segment."""
    
    start: float
    end: float
    speaker: str  # "SPEAKER_00", "SPEAKER_01", etc.
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "start": self.start,
            "end": self.end,
            "speaker": self.speaker,
        }


@dataclass
class DiarizationOutput:
    """Diarization stage output."""
    
    enabled: bool
    segments: List[SpeakerSegment]
    primary_speaker: Optional[str]
    num_speakers: int
    fallback_mode: bool  # True if using LLM fallback
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "segments": [s.to_dict() for s in self.segments],
            "primary_speaker": self.primary_speaker,
            "num_speakers": self.num_speakers,
            "fallback_mode": self.fallback_mode,
        }


def run_pyannote_diarization(audio_path: Path) -> List[SpeakerSegment]:
    """
    Run pyannote speaker diarization.
    
    Requires HF_TOKEN environment variable.
    Model: pyannote/speaker-diarization-community-1 (CC-BY-4.0, gated)
    
    Returns:
        List of speaker segments
    """
    if not DIARIZATION_ENABLED:
        raise RuntimeError("Diarization not enabled: HF_TOKEN not set")
    
    logger.info(f"Running pyannote diarization on {audio_path}")
    
    # Load pipeline with HF token
    pipeline = Pipeline.from_pretrained(
        "pyannote/speaker-diarization-3.1",
        use_auth_token=HF_TOKEN
    )
    
    # Run diarization
    diarization = pipeline(str(audio_path))
    
    # Convert to segments
    segments = []
    for turn, _, speaker in diarization.itertracks(yield_label=True):
        segment = SpeakerSegment(
            start=turn.start,
            end=turn.end,
            speaker=speaker
        )
        segments.append(segment)
    
    logger.info(f"Diarization completed: {len(segments)} segments")
    return segments


def identify_primary_speaker(segments: List[SpeakerSegment]) -> Optional[str]:
    """
    Identify primary speaker: speaker with most total speech time.
    
    Per SPEC §6.3: Primary speaker is used to separate questioners from
    the main presenter in category 17 (Q&A Handling).
    """
    if not segments:
        return None
    
    # Calculate total speech time per speaker
    speaker_time = {}
    for seg in segments:
        duration = seg.end - seg.start
        speaker_time[seg.speaker] = speaker_time.get(seg.speaker, 0) + duration
    
    # Find speaker with most time
    primary = max(speaker_time.items(), key=lambda x: x[1])[0]
    logger.info(f"Primary speaker: {primary} ({speaker_time[primary]:.1f}s total)")
    
    return primary


def create_fallback_output() -> DiarizationOutput:
    """
    Create fallback diarization output when HF_TOKEN is absent.
    
    Per SPEC §6.3 and ADR-009: Without diarization, the LLM will spot
    "repeat the question" phrases for Q&A detection, with confidence
    capped at 0.6 (H).
    """
    logger.info("Creating fallback diarization output (no HF_TOKEN)")
    
    return DiarizationOutput(
        enabled=False,
        segments=[],
        primary_speaker=None,
        num_speakers=0,
        fallback_mode=True,
    )


def diarize_audio(
    audio_path: Path,
    output_dir: Path,
    session_id: str,
) -> DiarizationOutput:
    """
    Main diarization function: pyannote or fallback.
    
    Args:
        audio_path: Path to audio16k.wav from ingest
        output_dir: Directory for output artifacts
        session_id: Session ID for tracking
    
    Returns:
        DiarizationOutput with speaker segments or fallback
    """
    logger.info(f"Starting diarization for session {session_id}")
    
    # Check if diarization is enabled
    if not DIARIZATION_ENABLED:
        output = create_fallback_output()
    else:
        try:
            # Run pyannote diarization
            segments = run_pyannote_diarization(audio_path)
            
            # Identify primary speaker
            primary_speaker = identify_primary_speaker(segments)
            
            # Count unique speakers
            num_speakers = len(set(seg.speaker for seg in segments))
            
            output = DiarizationOutput(
                enabled=True,
                segments=segments,
                primary_speaker=primary_speaker,
                num_speakers=num_speakers,
                fallback_mode=False,
            )
            
            logger.info(f"Diarization completed: {num_speakers} speakers, "
                       f"{len(segments)} segments")
            
        except Exception as e:
            logger.error(f"Diarization failed: {e}")
            # Fall back to LLM-based Q&A detection
            output = create_fallback_output()
    
    # Save output
    output_path = output_dir / f"{session_id}_diarization.json"
    with open(output_path, "w") as f:
        json.dump(output.to_dict(), f, indent=2)
    
    return output
