"""Alignment stage: WhisperX forced alignment + Silero VAD + gap-filler detector.

Per SPEC §6.3 and issue #21:
- WhisperX forced alignment with wav2vec2 models for precise word boundaries
- Silero VAD for speech/non-speech segmentation  
- Gap detector: re-decode speech gaps > 300ms to recover dropped fillers
- Acoustic fallback for gaps: label as filler_candidate with low confidence
"""

import json
import logging
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import torch
import whisperx

logger = logging.getLogger(__name__)

# Gap detection threshold (per SPEC §6.3)
GAP_THRESHOLD_MS = 300  # Re-decode speech gaps longer than this

# Wav2vec2 models for alignment per language
ALIGNMENT_MODELS = {
    "en": "facebook/wav2vec2-large-960h-lv60-self",
    "pt": "jonatasgrosman/wav2vec2-large-xlsr-53-portuguese",
}


@dataclass
class AlignedWord:
    """Word with aligned timing from wav2vec2."""
    
    word: str
    start: float
    end: float
    score: float  # Alignment confidence
    source: str  # "whisper_asr", "gap_detector", "acoustic_fallback"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "word": self.word,
            "start": self.start,
            "end": self.end,
            "score": self.score,
            "source": self.source,
        }


@dataclass
class VADSegment:
    """Voice activity detection segment."""
    
    start: float
    end: float
    is_speech: bool
    confidence: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "start": self.start,
            "end": self.end,
            "is_speech": self.is_speech,
            "confidence": self.confidence,
        }


@dataclass
class AlignmentOutput:
    """Alignment stage output."""
    
    aligned_words: List[AlignedWord]
    vad_segments: List[VADSegment]
    gap_fills_count: int
    acoustic_fallback_count: int
    mean_alignment_score: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "aligned_words": [w.to_dict() for w in self.aligned_words],
            "vad_segments": [s.to_dict() for s in self.vad_segments],
            "gap_fills_count": self.gap_fills_count,
            "acoustic_fallback_count": self.acoustic_fallback_count,
            "mean_alignment_score": self.mean_alignment_score,
        }


def load_silero_vad():
    """Load Silero VAD model."""
    try:
        model, utils = torch.hub.load(
            repo_or_dir='snakers4/silero-vad',
            model='silero_vad',
            force_reload=False,
            onnx=False
        )
        (get_speech_timestamps, _, read_audio, *_) = utils
        return model, get_speech_timestamps, read_audio
    except Exception as e:
        logger.error(f"Failed to load Silero VAD: {e}")
        raise


def run_vad(audio_path: Path, model, get_speech_timestamps, read_audio) -> List[VADSegment]:
    """
    Run Silero VAD on audio to detect speech/non-speech segments.
    
    Returns:
        List of VAD segments with is_speech flag
    """
    logger.info(f"Running Silero VAD on {audio_path}")
    
    # Load audio for VAD (16kHz required)
    wav = read_audio(str(audio_path), sampling_rate=16000)
    
    # Get speech timestamps
    speech_timestamps = get_speech_timestamps(
        wav,
        model,
        sampling_rate=16000,
        threshold=0.5,
        min_speech_duration_ms=250,
        min_silence_duration_ms=100,
    )
    
    # Convert to VADSegment objects (times in seconds)
    vad_segments = []
    for ts in speech_timestamps:
        segment = VADSegment(
            start=ts['start'] / 16000.0,
            end=ts['end'] / 16000.0,
            is_speech=True,
            confidence=1.0,  # Silero doesn't provide per-segment confidence
        )
        vad_segments.append(segment)
    
    logger.info(f"VAD detected {len(vad_segments)} speech segments")
    return vad_segments


def align_words_whisperx(
    audio_path: Path,
    transcript_segments: List[Dict[str, Any]],
    language: str,
    device: str = "cpu"
) -> List[AlignedWord]:
    """
    Use WhisperX to align words with wav2vec2 models.
    
    Args:
        audio_path: Path to audio16k.wav
        transcript_segments: Segments from ASR with words
        language: Language code (en, pt)
        device: "cpu" or "cuda"
    
    Returns:
        List of aligned words with precise boundaries
    """
    logger.info(f"Aligning words with WhisperX for language: {language}")
    
    # Map language code
    lang_code = language if language in ["en", "pt"] else "en"
    
    # Load alignment model for language
    model_name = ALIGNMENT_MODELS.get(lang_code, ALIGNMENT_MODELS["en"])
    logger.info(f"Using alignment model: {model_name}")
    
    model_a, metadata = whisperx.load_align_model(
        language_code=lang_code,
        device=device,
        model_name=model_name
    )
    
    # Load audio
    import whisperx
    audio = whisperx.load_audio(str(audio_path))
    
    # Align transcript
    result = whisperx.align(
        transcript_segments,
        model_a,
        metadata,
        audio,
        device,
        return_char_alignments=False
    )
    
    # Extract aligned words
    aligned_words = []
    for segment in result.get("segments", []):
        for word_info in segment.get("words", []):
            word = AlignedWord(
                word=word_info["word"],
                start=word_info["start"],
                end=word_info["end"],
                score=word_info.get("score", 1.0),
                source="whisper_asr"
            )
            aligned_words.append(word)
    
    logger.info(f"Aligned {len(aligned_words)} words")
    return aligned_words


def detect_gaps(
    aligned_words: List[AlignedWord],
    vad_segments: List[VADSegment],
    threshold_ms: int = GAP_THRESHOLD_MS
) -> List[Tuple[float, float]]:
    """
    Detect speech gaps > threshold_ms that may contain dropped fillers.
    
    Returns:
        List of (start, end) tuples for gaps to re-decode
    """
    gaps = []
    threshold_s = threshold_ms / 1000.0
    
    # Find gaps between aligned words
    for i in range(len(aligned_words) - 1):
        gap_start = aligned_words[i].end
        gap_end = aligned_words[i + 1].start
        gap_duration = gap_end - gap_start
        
        if gap_duration > threshold_s:
            # Check if gap overlaps with VAD speech regions
            gap_has_speech = any(
                vad.is_speech and vad.start < gap_end and vad.end > gap_start
                for vad in vad_segments
            )
            
            if gap_has_speech:
                gaps.append((gap_start, gap_end))
    
    logger.info(f"Detected {len(gaps)} speech gaps > {threshold_ms}ms")
    return gaps


def fill_gaps_acoustic(
    gaps: List[Tuple[float, float]],
    aligned_words: List[AlignedWord]
) -> Tuple[List[AlignedWord], int]:
    """
    Fill detected gaps with acoustic fallback placeholders.
    
    Per SPEC §6.3: When gap-detector can't confidently transcribe a gap,
    insert a filler_candidate with low confidence and source=acoustic_fallback.
    
    Returns:
        (updated_words, acoustic_fallback_count)
    """
    updated_words = list(aligned_words)
    fallback_count = 0
    
    for gap_start, gap_end in gaps:
        # Insert acoustic fallback placeholder
        filler_word = AlignedWord(
            word="[filler_candidate]",
            start=gap_start,
            end=gap_end,
            score=0.3,  # Low confidence (H)
            source="acoustic_fallback"
        )
        
        # Find insertion point
        insert_idx = 0
        for i, word in enumerate(updated_words):
            if word.start > gap_start:
                insert_idx = i
                break
        
        updated_words.insert(insert_idx, filler_word)
        fallback_count += 1
    
    # Sort by start time
    updated_words.sort(key=lambda w: w.start)
    
    logger.info(f"Added {fallback_count} acoustic fallback placeholders")
    return updated_words, fallback_count


def align_transcript(
    audio_path: Path,
    transcript_path: Path,
    output_dir: Path,
    session_id: str,
    language: str = "en"
) -> AlignmentOutput:
    """
    Main alignment function: WhisperX + VAD + gap detection.
    
    Args:
        audio_path: Path to audio16k.wav from ingest
        transcript_path: Path to transcript.json from ASR
        output_dir: Directory for output artifacts
        session_id: Session ID for tracking
        language: Language code (en, pt-BR, auto)
    
    Returns:
        AlignmentOutput with aligned words and VAD segments
    """
    logger.info(f"Starting alignment for session {session_id}")
    
    # Load transcript from ASR
    with open(transcript_path) as f:
        transcript_data = json.load(f)
    
    segments = transcript_data.get("segments", [])
    detected_language = transcript_data.get("language", language)
    
    # Map language code (pt-BR → pt)
    lang_code = detected_language
    if lang_code.startswith("pt"):
        lang_code = "pt"
    elif not lang_code in ["en", "pt"]:
        lang_code = "en"
    
    logger.info(f"Using language: {lang_code}")
    
    # 1. Load Silero VAD
    vad_model, get_speech_timestamps, read_audio = load_silero_vad()
    
    # 2. Run VAD
    vad_segments = run_vad(audio_path, vad_model, get_speech_timestamps, read_audio)
    
    # 3. Align words with WhisperX
    aligned_words = align_words_whisperx(
        audio_path=audio_path,
        transcript_segments=segments,
        language=lang_code,
        device="cpu"  # CPU-only per ADR-008
    )
    
    # 4. Detect gaps
    gaps = detect_gaps(aligned_words, vad_segments)
    
    # 5. Fill gaps with acoustic fallback (Phase 1 simplified)
    # Future: Use gap-detector re-decoding here
    aligned_words, acoustic_fallback_count = fill_gaps_acoustic(gaps, aligned_words)
    gap_fills_count = len(gaps)
    
    # Calculate mean alignment score
    scores = [w.score for w in aligned_words if w.source == "whisper_asr"]
    mean_alignment_score = sum(scores) / len(scores) if scores else 0.0
    
    # Save output
    output = AlignmentOutput(
        aligned_words=aligned_words,
        vad_segments=vad_segments,
        gap_fills_count=gap_fills_count,
        acoustic_fallback_count=acoustic_fallback_count,
        mean_alignment_score=mean_alignment_score,
    )
    
    output_path = output_dir / f"{session_id}_alignment.json"
    with open(output_path, "w") as f:
        json.dump(output.to_dict(), f, indent=2)
    
    logger.info(f"Alignment completed: {len(aligned_words)} words, "
                f"{gap_fills_count} gaps detected, "
                f"{acoustic_fallback_count} acoustic fallbacks")
    
    return output
