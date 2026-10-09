"""Celery worker for Stage Coach analysis pipeline.

Phase 1: Ingest and ASR stages.
"""

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Optional

from celery import Celery

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

app = Celery(
    "stagecoach",
    broker=REDIS_URL,
    backend=REDIS_URL,
)

# Configure Celery
app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,  # Acknowledge after task completes
    task_reject_on_worker_lost=True,
    task_default_queue="cpu",
    task_routes={
        "tasks.health_check": {"queue": "cpu"},
        "tasks.ingest": {"queue": "cpu"},
        "tasks.asr": {"queue": "cpu"},  # CPU-only per ADR-008
        "tasks.audio_features": {"queue": "cpu"},
        "tasks.vision": {"queue": "cpu"},
        "tasks.slides": {"queue": "cpu"},
        "tasks.content_llm": {"queue": "llm"},
        "tasks.fusion_scoring": {"queue": "cpu"},
        "tasks.report": {"queue": "cpu"},
    },
)


@app.task(name="tasks.health_check")
def health_check():
    """Health check task for worker verification."""
    return {"status": "healthy", "worker": "celery"}


@app.task(name="tasks.ingest", bind=True, max_retries=3)
def ingest_task(self, input_path: str, output_dir: str, session_id: str):
    """Ingest stage: validation, transcoding, modality detection.
    
    Args:
        input_path: Path to uploaded media file
        output_dir: Directory for output artifacts
        session_id: Session ID for tracking
        
    Returns:
        Dict with ingest output (media_info, modality, artifacts, sha256)
    """
    from pipeline.stages.ingest import ingest
    
    logger = logging.getLogger(__name__)
    logger.info(f"Starting ingest task for session {session_id}")
    
    try:
        result = ingest(
            input_path=Path(input_path),
            output_dir=Path(output_dir),
            session_id=session_id,
        )
        
        return result.to_dict()
        
    except Exception as exc:
        logger.error(f"Ingest failed for {session_id}: {exc}")
        # Retry with exponential backoff: 4s, 16s, 64s
        raise self.retry(exc=exc, countdown=4 ** self.request.retries)


@app.task(name="tasks.asr", bind=True, max_retries=3)
def asr_task(
    self,
    audio_path: str,
    output_dir: str,
    session_id: str,
    language: Optional[str] = None,
    model_name: Optional[str] = None,
):
    """ASR stage: Speech-to-text with faster-whisper.
    
    Args:
        audio_path: Path to audio16k.wav from ingest
        output_dir: Directory for output artifacts
        session_id: Session ID for tracking
        language: Language code (en, pt, auto) or None for auto-detect
        model_name: Model name override (tiny, small, medium, large-v3)
        
    Returns:
        Dict with transcript output
    """
    from pipeline.stages.asr import transcribe_audio
    
    logger = logging.getLogger(__name__)
    logger.info(f"Starting ASR task for session {session_id}")
    
    try:
        result = transcribe_audio(
            audio_path=Path(audio_path),
            output_dir=Path(output_dir),
            session_id=session_id,
            language=language,
            model_name=model_name,
        )
        
        return result.to_dict()
        
    except Exception as exc:
        logger.error(f"ASR failed for {session_id}: {exc}")
        # Retry with exponential backoff: 4s, 16s, 64s
        raise self.retry(exc=exc, countdown=4 ** self.request.retries)


@app.task(name="tasks.content_llm", bind=True, max_retries=3)
def content_llm_task(
    self,
    transcript_path: str,
    output_dir: str,
    session_id: str,
    context_type: str = "keynote",
    language: str = "en",
    audience_desc: Optional[str] = None,
    max_duration_s: float = 5400.0,
):
    """Content LLM stage: structured text analysis per §6.7.
    
    Issues #27, #28, #29.
    
    Args:
        transcript_path: Path to transcript.json from ASR
        output_dir: Directory for output artifacts
        session_id: Session ID
        context_type: Context type (keynote, exec_briefing, etc.)
        language: Language code (en or pt-BR)
        audience_desc: Optional audience description
        max_duration_s: Media duration for validation
        
    Returns:
        Dict with content LLM output
    """
    from pipeline.stages.content_llm import content_llm_stage
    
    logger = logging.getLogger(__name__)
    logger.info(f"Starting content_llm task for session {session_id}")
    
    try:
        result = content_llm_stage(
            transcript_path=Path(transcript_path),
            output_dir=Path(output_dir),
            session_id=session_id,
            context_type=context_type,
            language=language,
            audience_desc=audience_desc,
            max_duration_s=max_duration_s,
        )
        
        return result.to_dict()
        
    except Exception as exc:
        logger.error(f"content_llm failed for {session_id}: {exc}")
        # Retry with exponential backoff: 4s, 16s, 64s
        raise self.retry(exc=exc, countdown=4 ** self.request.retries)
