"""Celery worker for Stage Coach analysis pipeline.

Phase 1: Ingest, ASR, alignment, diarization with DAG orchestration and progress tracking.
"""

import json
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

import redis
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
        "tasks.alignment": {"queue": "cpu"},  # WhisperX alignment
        "tasks.diarization": {"queue": "cpu"},  # pyannote diarization
        "tasks.audio_features": {"queue": "cpu"},
        "tasks.vision": {"queue": "cpu"},
        "tasks.slides": {"queue": "cpu"},
        "tasks.content_llm": {"queue": "llm"},
        "tasks.fusion_scoring": {"queue": "cpu"},
        "tasks.report": {"queue": "cpu"},
    },
)


def emit_progress(
    job_id: str,
    stage: str,
    status: str,
    pct: Optional[float] = None,
    eta_s: Optional[int] = None,
    message: Optional[str] = None,
):
    """Emit progress event to Redis for SSE streaming (issue #19)."""
    r = redis.from_url(REDIS_URL)
    event = {
        "stage": stage,
        "status": status,
        "pct": pct,
        "eta_s": eta_s,
        "message": message,
        "timestamp": datetime.utcnow().isoformat(),
    }
    channel = f"progress:{job_id}"
    r.publish(channel, json.dumps(event))
    logging.info(f"Progress published to {channel}: {status}")


@app.task(name="tasks.health_check")
def health_check():
    """Health check task for worker verification."""
    return {"status": "healthy", "worker": "celery"}


@app.task(name="tasks.ingest", bind=True, max_retries=3)
def ingest_task(self, input_path: str, output_dir: str, session_id: str, job_id: Optional[str] = None):
    """Ingest stage: validation, transcoding, modality detection.
    
    Args:
        input_path: Path to uploaded media file
        output_dir: Directory for output artifacts
        session_id: Session ID for tracking
        job_id: Analysis job ID for progress tracking
        
    Returns:
        Dict with ingest output (media_info, modality, artifacts, sha256)
        and audio_path for chaining to ASR
    """
    from pipeline.stages.ingest import ingest
    
    logger = logging.getLogger(__name__)
    logger.info(f"Starting ingest task for session {session_id}")
    
    if job_id:
        emit_progress(job_id, "ingest", "running", pct=0, message="Validating and transcoding media")
    
    try:
        result = ingest(
            input_path=Path(input_path),
            output_dir=Path(output_dir),
            session_id=session_id,
        )
        
        output_dict = result.to_dict()
        
        # Extract audio path for chaining
        audio_path = str(result.artifacts.get("audio16k"))
        output_dict["audio_path"] = audio_path
        
        if job_id:
            emit_progress(job_id, "ingest", "succeeded", pct=100, message="Media ingested successfully")
        
        logger.info(f"Ingest completed for {session_id}")
        return output_dict
        
    except Exception as exc:
        logger.error(f"Ingest failed for {session_id}: {exc}")
        if job_id:
            emit_progress(job_id, "ingest", "failed", message=f"Ingest failed: {str(exc)}")
        # Retry with exponential backoff: 4s, 16s, 64s
        raise self.retry(exc=exc, countdown=4 ** self.request.retries)


@app.task(name="tasks.asr", bind=True, max_retries=3)
def asr_task(
    self,
    ingest_result: dict,
    output_dir: str,
    session_id: str,
    language: Optional[str] = None,
    model_name: Optional[str] = None,
    job_id: Optional[str] = None,
):
    """ASR stage: Speech-to-text with faster-whisper.
    
    Args:
        ingest_result: Dict from ingest task with audio_path
        output_dir: Directory for output artifacts
        session_id: Session ID for tracking
        language: Language code (en, pt, auto) or None for auto-detect
        model_name: Model name override (tiny, small, medium, large-v3)
        job_id: Analysis job ID for progress tracking
        
    Returns:
        Dict with transcript output
    """
    from pipeline.stages.asr import transcribe_audio
    
    logger = logging.getLogger(__name__)
    logger.info(f"Starting ASR task for session {session_id}")
    
    audio_path = ingest_result.get("audio_path")
    if not audio_path:
        raise ValueError("No audio_path in ingest result")
    
    if job_id:
        emit_progress(job_id, "asr", "running", pct=0, message="Transcribing audio")
    
    try:
        result = transcribe_audio(
            audio_path=Path(audio_path),
            output_dir=Path(output_dir),
            session_id=session_id,
            language=language,
            model_name=model_name,
        )
        
        output_dict = result.to_dict()
        # Add transcript_path to output for verification
        output_dict["transcript_path"] = str(Path(output_dir) / "transcript.json")
        
        # Add transcript path for chaining to alignment
        transcript_path = Path(output_dir) / f"{session_id}_transcript.json"
        with open(transcript_path, "w") as f:
            json.dump(output_dict, f)
        output_dict["transcript_path"] = str(transcript_path)
        output_dict["audio_path"] = audio_path  # Pass through for alignment
        
        if job_id:
            emit_progress(job_id, "asr", "succeeded", pct=100, message="Transcription completed")
        
        logger.info(f"ASR completed for {session_id}")
        return output_dict
        
    except Exception as exc:
        logger.error(f"ASR failed for {session_id}: {exc}")
        if job_id:
            emit_progress(job_id, "asr", "failed", message=f"ASR failed: {str(exc)}")
        # Retry with exponential backoff: 4s, 16s, 64s
        raise self.retry(exc=exc, countdown=4 ** self.request.retries)


@app.task(name="tasks.alignment", bind=True, max_retries=3)
def alignment_task(
    self,
    asr_result: dict,
    output_dir: str,
    session_id: str,
    job_id: Optional[str] = None,
):
    """Alignment stage: WhisperX forced alignment + VAD + gap detection.
    
    Args:
        asr_result: Dict from ASR task with transcript_path and audio_path
        output_dir: Directory for output artifacts
        session_id: Session ID for tracking
        job_id: Analysis job ID for progress tracking
        
    Returns:
        Dict with alignment output plus audio_path for diarization
    """
    from pipeline.stages.alignment import align_transcript
    
    logger = logging.getLogger(__name__)
    logger.info(f"Starting alignment task for session {session_id}")
    
    audio_path = asr_result.get("audio_path")
    transcript_path = asr_result.get("transcript_path")
    language = asr_result.get("language", "en")
    
    if not audio_path or not transcript_path:
        raise ValueError("Missing audio_path or transcript_path in ASR result")
    
    if job_id:
        emit_progress(job_id, "alignment", "running", pct=0, message="Aligning words with WhisperX")
    
    try:
        result = align_transcript(
            audio_path=Path(audio_path),
            transcript_path=Path(transcript_path),
            output_dir=Path(output_dir),
            session_id=session_id,
            language=language,
        )
        
        output_dict = result.to_dict()
        output_dict["audio_path"] = audio_path  # Pass through for diarization
        
        if job_id:
            emit_progress(job_id, "alignment", "succeeded", pct=100, message="Word alignment completed")
        
        logger.info(f"Alignment completed for {session_id}")
        return output_dict
        
    except Exception as exc:
        logger.error(f"Alignment failed for {session_id}: {exc}")
        if job_id:
            emit_progress(job_id, "alignment", "failed", message=f"Alignment failed: {str(exc)}")
        # Retry with exponential backoff: 4s, 16s, 64s
        raise self.retry(exc=exc, countdown=4 ** self.request.retries)


@app.task(name="tasks.diarization", bind=True, max_retries=3)
def diarization_task(
    self,
    alignment_result: dict,
    output_dir: str,
    session_id: str,
    job_id: Optional[str] = None,
):
    """Diarization stage: pyannote speaker diarization (gated on HF_TOKEN).
    
    Args:
        alignment_result: Dict from alignment task with audio_path
        output_dir: Directory for output artifacts
        session_id: Session ID for tracking
        job_id: Analysis job ID for progress tracking
        
    Returns:
        Dict with diarization output
    """
    from pipeline.stages.diarization import diarize_audio, DIARIZATION_ENABLED
    
    logger = logging.getLogger(__name__)
    logger.info(f"Starting diarization task for session {session_id}")
    
    audio_path = alignment_result.get("audio_path")
    if not audio_path:
        raise ValueError("Missing audio_path in alignment result")
    
    # Check if diarization is enabled
    if not DIARIZATION_ENABLED:
        if job_id:
            emit_progress(job_id, "diarization", "skipped", pct=100, 
                         message="Diarization skipped (no HF_TOKEN), using LLM fallback")
        logger.info("Diarization skipped: HF_TOKEN not set")
    else:
        if job_id:
            emit_progress(job_id, "diarization", "running", pct=0, message="Running speaker diarization")
    
    try:
        result = diarize_audio(
            audio_path=Path(audio_path),
            output_dir=Path(output_dir),
            session_id=session_id,
        )
        
        output_dict = result.to_dict()
        
        # Mark as skipped if fallback mode
        status = "skipped" if result.fallback_mode else "succeeded"
        
        if job_id:
            emit_progress(job_id, "diarization", status, pct=100,
                         message="Speaker diarization completed" if not result.fallback_mode 
                                else "Using LLM fallback for Q&A detection")
        
        logger.info(f"Diarization task completed for {session_id}")
        return output_dict
        
    except Exception as exc:
        logger.error(f"Diarization failed for {session_id}: {exc}")
        if job_id:
            emit_progress(job_id, "diarization", "failed", message=f"Diarization failed: {str(exc)}")
        # Retry with exponential backoff: 4s, 16s, 64s
        raise self.retry(exc=exc, countdown=4 ** self.request.retries)
