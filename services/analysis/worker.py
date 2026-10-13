"""Celery worker for Stage Coach analysis pipeline.

Phase 1: Ingest, ASR, alignment, diarization with DAG orchestration and progress tracking.
"""

import json
import logging
import os
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import redis
from celery import Celery
from celery.signals import worker_process_init
from sqlalchemy import create_engine, text

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


@worker_process_init.connect(weak=False)
def init_telemetry(*args, **kwargs):
    # Exporter threads do not survive the prefork fork, so each child starts its own.
    if not os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
        return
    try:
        from splunk_otel import init_splunk_otel
    except ImportError:
        return
    try:
        init_splunk_otel()
    except Exception:
        logging.getLogger(__name__).exception("OpenTelemetry failed to start")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
DATABASE_URL = os.getenv("DATABASE_URL", "")

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


def _set_job_state(job_id: str, session_id: str, status: str, error: Optional[dict] = None) -> None:
    """Persist terminal/background state without logging user media or transcript."""
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is required for job persistence")
    engine = create_engine(DATABASE_URL)
    now = datetime.utcnow()
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE analysis_jobs
                SET status = :status,
                    started_at = COALESCE(started_at, :now),
                    finished_at = CASE WHEN :status IN ('succeeded', 'failed', 'partial')
                                       THEN :now ELSE finished_at END,
                    error = CAST(:error AS JSONB)
                WHERE id = CAST(:job_id AS UUID)
                """
            ),
            {
                "status": status,
                "now": now,
                "error": json.dumps(error) if error else None,
                "job_id": job_id,
            },
        )
        conn.execute(
            text(
                """
                UPDATE sessions
                SET status = :session_status, updated_at = :now
                WHERE id = CAST(:session_id AS UUID)
                """
            ),
            {
                "session_status": {
                    "running": "processing",
                    "succeeded": "ready",
                    "partial": "partial",
                    "failed": "failed",
                }.get(status, status),
                "now": now,
                "session_id": session_id,
            },
        )


def _record_job_step(
    *,
    job_id: str,
    stage: str,
    status: str,
    started_at: datetime,
    outputs: Optional[dict] = None,
    metrics: Optional[dict] = None,
    error: Optional[dict] = None,
) -> None:
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is required for job persistence")
    engine = create_engine(DATABASE_URL)
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO job_steps (
                    id, job_id, stage, stage_version, status, attempt,
                    output_uris, metrics, started_at, finished_at, error, created_at
                ) VALUES (
                    CAST(:id AS UUID), CAST(:job_id AS UUID), :stage, '1.0.0', :status, 1,
                    CAST(:outputs AS JSONB), CAST(:metrics AS JSONB), :started_at, :finished_at,
                    CAST(:error AS JSONB), :created_at
                )
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "job_id": job_id,
                "stage": stage,
                "status": status,
                "outputs": json.dumps(outputs) if outputs else None,
                "metrics": json.dumps(metrics) if metrics else None,
                "started_at": started_at,
                "finished_at": datetime.utcnow(),
                "error": json.dumps(error) if error else None,
                "created_at": started_at,
            },
        )


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


@app.task(name="tasks.audio_features", bind=True, max_retries=3)
def audio_features_task(
    self,
    asr_result: dict,
    output_dir: str,
    session_id: str,
    job_id: Optional[str] = None,
):
    """Audio-features stage: F0, PVQ, intensity, syllables, pauses, SNR.

    Issue #24, SPEC §6.4. Runs on un-normalized audio16k.wav.
    """
    from pipeline.stages.audio_features import extract_audio_features

    logger = logging.getLogger(__name__)
    logger.info(f"Starting audio_features task for session {session_id}")

    audio_path = Path(output_dir) / "audio16k.wav"
    if not audio_path.exists() and isinstance(asr_result, dict):
        maybe = asr_result.get("audio_path")
        if maybe:
            audio_path = Path(maybe)

    transcript_path = None
    if isinstance(asr_result, dict) and asr_result.get("transcript_path"):
        transcript_path = Path(asr_result["transcript_path"])

    if job_id:
        emit_progress(job_id, "audio_features", "running", pct=0, message="Extracting prosody")

    try:
        result = extract_audio_features(
            audio_path=audio_path,
            output_dir=Path(output_dir),
            session_id=session_id,
            transcript_path=transcript_path,
        )
        if job_id:
            emit_progress(
                job_id,
                "audio_features",
                "succeeded",
                pct=100,
                message="Prosody features extracted",
            )
        logger.info(f"audio_features completed for {session_id}")
        return result.to_dict()
    except Exception as exc:
        logger.error(f"audio_features failed for {session_id}: {exc}")
        if job_id:
            emit_progress(job_id, "audio_features", "failed", message=f"audio_features failed: {str(exc)}")
        raise self.retry(exc=exc, countdown=4 ** self.request.retries)


@app.task(name="tasks.run_mvp_analysis", bind=True, max_retries=1)
def run_mvp_analysis_task(
    self,
    *,
    job_id: str,
    session_id: str,
    input_path: str,
    output_dir: str,
    context_type: str,
    language: str,
    slot_min: Optional[int] = None,
):
    """Run the private-beta ingest → ASR → audio → partial-report pipeline."""
    from pipeline.stages.asr import transcribe_audio
    from pipeline.stages.audio_features import extract_audio_features
    from pipeline.stages.ingest import ingest
    from pipeline.stages.mvp_report import build_mvp_report

    logger = logging.getLogger(__name__)
    source = Path(input_path)
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    _set_job_state(job_id, session_id, "running")

    try:
        started = datetime.utcnow()
        emit_progress(job_id, "ingest", "running", pct=5, message="Validating media")
        ingest_result = ingest(source, destination, session_id)
        ingest_dict = ingest_result.to_dict()
        _record_job_step(
            job_id=job_id,
            stage="ingest",
            status="succeeded",
            started_at=started,
            outputs=ingest_dict["artifacts"],
            metrics=ingest_dict["media_info"],
        )
        emit_progress(job_id, "ingest", "succeeded", pct=25, message="Media prepared")

        started = datetime.utcnow()
        emit_progress(job_id, "asr", "running", pct=30, message="Transcribing speech")
        asr_language = "pt" if language == "pt-BR" else (None if language == "auto" else language)
        transcript = transcribe_audio(
            audio_path=Path(ingest_dict["artifacts"]["audio16k"]),
            output_dir=destination,
            session_id=session_id,
            language=asr_language,
        )
        transcript_path = destination / "transcript.json"
        _record_job_step(
            job_id=job_id,
            stage="asr",
            status="succeeded",
            started_at=started,
            outputs={"transcript": str(transcript_path)},
            metrics={
                "language": transcript.language,
                "word_count": transcript.word_count,
                "mean_word_probability": transcript.mean_word_probability,
            },
        )
        emit_progress(job_id, "asr", "succeeded", pct=60, message="Transcript ready")

        started = datetime.utcnow()
        emit_progress(
            job_id,
            "audio_features",
            "running",
            pct=65,
            message="Measuring pace and vocal variation",
        )
        audio = extract_audio_features(
            audio_path=Path(ingest_dict["artifacts"]["audio16k"]),
            output_dir=destination,
            session_id=session_id,
            transcript_path=transcript_path,
        )
        _record_job_step(
            job_id=job_id,
            stage="audio_features",
            status="succeeded",
            started_at=started,
            outputs=audio.artifacts,
            metrics={
                "pvq_median": audio.metrics.get("pvq_median"),
                "snr_db": audio.metrics.get("snr_db"),
                "confidence": audio.metrics.get("confidence"),
            },
        )
        emit_progress(
            job_id,
            "audio_features",
            "succeeded",
            pct=85,
            message="Audio measurements ready",
        )

        started = datetime.utcnow()
        emit_progress(job_id, "report", "running", pct=90, message="Building coaching report")
        resolved_language = "pt-BR" if transcript.language.startswith("pt") else "en"
        report_path = destination / "report.json"
        report = build_mvp_report(
            session_id=session_id,
            context_type=context_type,
            language=resolved_language,
            slot_min=slot_min,
            ingest=ingest_dict,
            transcript_path=transcript_path,
            audio_metrics_path=Path(audio.artifacts["audio_metrics"]),
            prosody_path=Path(audio.artifacts["prosody"]),
            packages_dir=Path("/packages"),
            output_path=report_path,
        )
        playback = ingest_dict["artifacts"].get("playback") or str(source)
        _record_job_step(
            job_id=job_id,
            stage="report",
            status="succeeded",
            started_at=started,
            outputs={
                "report": str(report_path),
                "transcript": str(transcript_path),
                "playback": playback,
            },
            metrics={
                "overall": report.get("overall"),
                "confidence": report.get("confidence"),
                "partial": True,
            },
        )
        _set_job_state(job_id, session_id, "partial")
        emit_progress(job_id, "report", "succeeded", pct=100, message="Report ready")
        logger.info("MVP analysis completed session=%s job=%s", session_id, job_id)
        return {"job_id": job_id, "session_id": session_id, "report_path": str(report_path)}
    except Exception as exc:
        safe_error = {"type": type(exc).__name__, "message": str(exc)[:500]}
        logger.exception("MVP analysis failed session=%s job=%s", session_id, job_id)
        _set_job_state(job_id, session_id, "failed", safe_error)
        emit_progress(job_id, "pipeline", "failed", message="Analysis failed")
        raise


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
