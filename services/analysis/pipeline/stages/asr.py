"""ASR stage: Speech-to-text with faster-whisper.

Per SPEC §6.3 and issue #20:
- faster-whisper BatchedInferencePipeline with word_timestamps=True
- Filler-preserving transcription with per-language initial prompts
- Language auto-detect (en, pt-BR) with confidence threshold
- Per-word probability tracking
- CPU-optimized: small/medium models with int8 quantization
- condition_on_previous_text=False to reduce hallucination
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Filler-preserving initial prompts per language
# Per SPEC §6.3: Whisper tends to drop fillers without these prompts
FILLER_PROMPTS = {
    "en": "Um, uh, er, like, you know, I mean, so, right, okay, basically, actually.",
    "pt": "Ãh, é, então, né, tipo, sabe, assim, bom, enfim, basicamente.",
}

# Language auto-detect confidence threshold
LANGUAGE_CONFIDENCE_THRESHOLD = 0.8

# Default model per compute environment
# Per ADR-008: CPU-only, use small/medium with int8
# In CI: use tiny model for speed
DEFAULT_MODEL = "small"
CI_MODEL = "tiny"


@dataclass
class Word:
    """Word-level transcription with timing and confidence."""
    
    word: str
    start: float
    end: float
    probability: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "word": self.word,
            "start": self.start,
            "end": self.end,
            "probability": self.probability,
        }


@dataclass
class Segment:
    """Segment-level transcription."""
    
    id: int
    text: str
    start: float
    end: float
    words: List[Word]
    avg_probability: float
    no_speech_prob: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "start": self.start,
            "end": self.end,
            "words": [w.to_dict() for w in self.words],
            "avg_probability": self.avg_probability,
            "no_speech_prob": self.no_speech_prob,
        }


@dataclass
class TranscriptOutput:
    """ASR stage output."""
    
    language: str
    language_probability: float
    model: str
    segments: List[Segment]
    duration: float
    word_count: int
    mean_word_probability: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "language": self.language,
            "language_probability": self.language_probability,
            "model": self.model,
            "segments": [s.to_dict() for s in self.segments],
            "duration": self.duration,
            "word_count": self.word_count,
            "mean_word_probability": self.mean_word_probability,
        }


def get_model_name(ci_mode: bool = False) -> str:
    """Get the appropriate model name based on environment.
    
    Args:
        ci_mode: If True, use tiny model for CI speed
        
    Returns:
        Model name for faster-whisper
    """
    import os
    
    # Check if we're in CI
    is_ci = os.getenv("CI") == "true" or ci_mode
    
    if is_ci:
        return CI_MODEL
    
    return os.getenv("ASR_MODEL", DEFAULT_MODEL)


def load_model(model_name: str, device: str = "cpu", compute_type: str = "int8"):
    """Load faster-whisper model.
    
    Per ADR-008: CPU-only with int8 quantization.
    
    Args:
        model_name: Model size (tiny, small, medium, large-v3)
        device: Device to run on (cpu or cuda)
        compute_type: Compute type (int8, float16, etc.)
        
    Returns:
        Loaded WhisperModel instance
    """
    from faster_whisper import WhisperModel
    
    logger.info(f"Loading faster-whisper model: {model_name} on {device} with {compute_type}")
    
    model = WhisperModel(
        model_name,
        device=device,
        compute_type=compute_type,
        cpu_threads=4,
        num_workers=1,
    )
    
    return model


def transcribe_audio(
    audio_path: Path,
    output_dir: Path,
    session_id: str,
    language: Optional[str] = None,
    model_name: Optional[str] = None,
) -> TranscriptOutput:
    """Transcribe audio with faster-whisper.
    
    Per SPEC §6.3 and issue #20:
    1. BatchedInferencePipeline with word_timestamps=True
    2. Filler-preserving prompts per language
    3. Language auto-detect if not specified
    4. condition_on_previous_text=False
    5. Per-word probability tracking
    
    Args:
        audio_path: Path to audio16k.wav from ingest
        output_dir: Output directory for transcript.json
        session_id: Session ID for logging
        language: Language code (en, pt) or None for auto-detect
        model_name: Model name override
        
    Returns:
        TranscriptOutput with segments and words
    """
    if model_name is None:
        model_name = get_model_name()
    
    logger.info(f"[{session_id}] Starting ASR with model {model_name}")
    
    # Load model
    model = load_model(model_name)
    
    # Language detection if needed
    if language is None or language == "auto":
        logger.info(f"[{session_id}] Detecting language...")
        
        # Detect language from first 30 seconds
        segments_detect, info = model.transcribe(
            str(audio_path),
            task="transcribe",
            beam_size=1,
            best_of=1,
            vad_filter=False,
            without_timestamps=True,
            language=None,
        )
        
        # Consume the generator to get info
        list(segments_detect)
        
        detected_lang = info.language if hasattr(info, 'language') else "en"
        lang_prob = info.language_probability if hasattr(info, 'language_probability') else 0.0
        
        logger.info(
            f"[{session_id}] Detected language: {detected_lang} "
            f"(confidence: {lang_prob:.2f})"
        )
        
        language = detected_lang
        language_probability = lang_prob
        
        # Warn if confidence is low
        if lang_prob < LANGUAGE_CONFIDENCE_THRESHOLD:
            logger.warning(
                f"[{session_id}] Low language confidence ({lang_prob:.2f}). "
                "User confirmation recommended before LLM stage."
            )
    else:
        language_probability = 1.0
    
    # Normalize language code
    if language.startswith("pt"):
        language = "pt"
    elif not language.startswith("en"):
        logger.warning(f"[{session_id}] Unsupported language {language}, falling back to en")
        language = "en"
    
    # Get filler prompt for language
    initial_prompt = FILLER_PROMPTS.get(language, FILLER_PROMPTS["en"])
    
    logger.info(f"[{session_id}] Transcribing with filler prompt: {initial_prompt[:50]}...")
    
    # Transcribe with word timestamps
    segments_raw, info = model.transcribe(
        str(audio_path),
        task="transcribe",
        language=language,
        beam_size=5,
        best_of=5,
        temperature=0.0,
        word_timestamps=True,
        condition_on_previous_text=False,
        initial_prompt=initial_prompt,
        vad_filter=True,
        vad_parameters={
            "threshold": 0.5,
            "min_speech_duration_ms": 250,
            "max_speech_duration_s": 60,
            "min_silence_duration_ms": 100,
        },
    )
    
    # Process segments
    segments = []
    all_words = []
    
    for seg_idx, segment in enumerate(segments_raw):
        # Extract words with probabilities
        words = []
        if hasattr(segment, 'words') and segment.words:
            for word in segment.words:
                word_obj = Word(
                    word=word.word.strip(),
                    start=word.start,
                    end=word.end,
                    probability=word.probability,
                )
                words.append(word_obj)
                all_words.append(word_obj)
        
        # Calculate average probability for segment
        if words:
            avg_prob = sum(w.probability for w in words) / len(words)
        else:
            avg_prob = 0.0
        
        seg_obj = Segment(
            id=seg_idx,
            text=segment.text.strip(),
            start=segment.start,
            end=segment.end,
            words=words,
            avg_probability=avg_prob,
            no_speech_prob=segment.no_speech_prob if hasattr(segment, 'no_speech_prob') else 0.0,
        )
        
        segments.append(seg_obj)
    
    # Calculate overall statistics
    duration = segments[-1].end if segments else 0.0
    word_count = len(all_words)
    mean_word_prob = sum(w.probability for w in all_words) / word_count if all_words else 0.0
    
    logger.info(
        f"[{session_id}] Transcription complete: "
        f"{len(segments)} segments, {word_count} words, "
        f"duration {duration:.1f}s, mean prob {mean_word_prob:.3f}"
    )
    
    # Create output
    output = TranscriptOutput(
        language=language,
        language_probability=language_probability,
        model=model_name,
        segments=segments,
        duration=duration,
        word_count=word_count,
        mean_word_probability=mean_word_prob,
    )
    
    # Write transcript.json
    output_path = output_dir / "transcript.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output.to_dict(), f, ensure_ascii=False, indent=2)
    
    logger.info(f"[{session_id}] Wrote transcript to {output_path}")
    
    return output
