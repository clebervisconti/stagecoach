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
from typing import Any, Optional

import redis
from celery import Celery
from celery.schedules import crontab
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
        "tasks.alignment": {"queue": "cpu"},  # WhisperX alignment
        "tasks.diarization": {"queue": "cpu"},  # pyannote diarization
        "tasks.audio_features": {"queue": "cpu"},
        "tasks.vision": {"queue": "cpu"},
        "tasks.slides": {"queue": "cpu"},
        "tasks.content_llm": {"queue": "llm"},
        "tasks.fusion_scoring": {"queue": "cpu"},
        "tasks.report": {"queue": "cpu"},
        "tasks.run_mvp_analysis": {"queue": "cpu"},
        "tasks.prepare_session": {"queue": "cpu"},
        "tasks.export_pdf": {"queue": "cpu"},
        "tasks.retention_sweeper": {"queue": "cpu"},
        "tasks.prep_llm": {"queue": "llm"},
    },
    beat_schedule={
        "retention-sweeper-nightly": {
            "task": "tasks.retention_sweeper",
            "schedule": crontab(hour=3, minute=17),
        },
    },
)


def _publish_event(job_id: str, event: dict) -> None:
    """Publish a SPEC §7.6 event onto the job's Redis progress channel."""
    r = redis.from_url(REDIS_URL)
    channel = f"progress:{job_id}"
    r.publish(channel, json.dumps(event))
    logging.info("Progress published to %s: %s", channel, event.get("type") or event.get("status"))


def emit_progress(
    job_id: str,
    stage: str,
    status: str,
    pct: Optional[float] = None,
    eta_s: Optional[int] = None,
    message: Optional[str] = None,
    session_id: Optional[str] = None,
):
    """Emit a `type: stage` progress event for SSE streaming (issues #19, #46)."""
    from pipeline.partial import stage_event

    _publish_event(
        job_id,
        stage_event(
            job_id,
            stage,
            status,
            session_id=session_id,
            pct=pct,
            eta_s=eta_s,
            message=message,
        ),
    )
    if status == "running":
        _note_running_stage(job_id, stage, message)


def emit_partial_ready(
    job_id: str,
    categories: list[str],
    session_id: Optional[str] = None,
) -> None:
    """Emit SPEC §7.6 `partial_ready` so the report can render scored categories live."""
    from pipeline.partial import partial_ready_event

    _publish_event(job_id, partial_ready_event(job_id, list(categories), session_id=session_id))


def emit_done(job_id: str, status: str, session_id: Optional[str] = None) -> None:
    """Emit SPEC §7.6 `done` when the job reaches a terminal report."""
    from pipeline.partial import done_event

    _publish_event(job_id, done_event(job_id, status, session_id=session_id))


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
                    "preparing": "preparing",
                    "layout_review": "layout_review",
                }.get(status, status),
                "now": now,
                "session_id": session_id,
            },
        )


def _sql_scalar(query: str, params: dict) -> Any:
    if not DATABASE_URL:
        return None
    engine = create_engine(DATABASE_URL)
    with engine.begin() as conn:
        return conn.execute(text(query), params).scalar()


def _confirmed_online_layouts(session_id: str) -> int:
    if not DATABASE_URL:
        return 0
    value = _sql_scalar(
        """
        SELECT COUNT(*)
        FROM session_layouts sl
        JOIN sessions s ON s.id = sl.session_id
        WHERE s.user_id = (SELECT user_id FROM sessions WHERE id = CAST(:sid AS UUID))
          AND s.delivery_mode <> 'stage'
          AND sl.status IN ('confirmed', 'auto_confirmed')
        """,
        {"sid": session_id},
    )
    return int(value or 0)


def _layout_review_pref(session_id: str) -> str:
    if not DATABASE_URL:
        return "when_unsure"
    value = _sql_scalar(
        """
        SELECT u.layout_review_pref
        FROM users u
        JOIN sessions s ON s.user_id = u.id
        WHERE s.id = CAST(:sid AS UUID)
        """,
        {"sid": session_id},
    )
    return str(value or "when_unsure")


def _persist_session_layout(
    *,
    session_id: str,
    job_id: str,
    layout: dict,
    status: str,
) -> None:
    if not DATABASE_URL:
        return
    engine = create_engine(DATABASE_URL)
    now = datetime.utcnow()
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO session_layouts (
                    id, session_id, job_id, version, status, detector_version,
                    confidence, detected, confirmed, edit_count, created_at, confirmed_at
                ) VALUES (
                    gen_random_uuid(), CAST(:sid AS UUID), CAST(:jid AS UUID),
                    :version, :status, :detector, :confidence,
                    CAST(:detected AS JSONB),
                    CAST(:confirmed AS JSONB),
                    0, :now,
                    CASE WHEN :status IN ('confirmed', 'auto_confirmed') THEN :now ELSE NULL END
                )
                ON CONFLICT (job_id, version) DO UPDATE SET
                    status = EXCLUDED.status,
                    confidence = EXCLUDED.confidence,
                    detected = EXCLUDED.detected,
                    confirmed = EXCLUDED.confirmed,
                    confirmed_at = EXCLUDED.confirmed_at
                """
            ),
            {
                "sid": session_id,
                "jid": job_id,
                "version": int(layout.get("version") or 1),
                "status": status,
                "detector": str(layout.get("detector_version") or "1.0.0"),
                "confidence": float(layout.get("confidence") or 0),
                "detected": json.dumps(layout),
                "confirmed": json.dumps(layout) if status in {"confirmed", "auto_confirmed"} else None,
                "now": now,
            },
        )


def _enqueue_mvp_analysis(kwargs: dict) -> None:
    run_mvp_analysis_task.apply_async(kwargs=kwargs, queue="cpu")


def _note_running_stage(job_id: str, stage: str, message: Optional[str]) -> None:
    """Persist the stage that is in progress so the report page can show it before it finishes."""
    if not DATABASE_URL:
        return
    now = datetime.utcnow()
    metrics = json.dumps({"message": message}) if message else None
    try:
        engine = create_engine(DATABASE_URL)
        with engine.begin() as conn:
            existing = conn.execute(
                text(
                    """
                    SELECT id, status FROM job_steps
                    WHERE job_id = CAST(:job_id AS UUID) AND stage = :stage
                    ORDER BY created_at DESC
                    LIMIT 1
                    """
                ),
                {"job_id": job_id, "stage": stage},
            ).first()
            if existing and existing.status not in {"succeeded", "failed", "skipped"}:
                conn.execute(
                    text(
                        """
                        UPDATE job_steps
                        SET status = 'running',
                            metrics = COALESCE(CAST(:metrics AS JSONB), metrics),
                            finished_at = NULL
                        WHERE id = CAST(:id AS UUID)
                        """
                    ),
                    {"id": str(existing.id), "metrics": metrics},
                )
                return
            if existing:
                return
            conn.execute(
                text(
                    """
                    INSERT INTO job_steps (
                        id, job_id, stage, stage_version, status, attempt,
                        metrics, started_at, finished_at, created_at
                    ) VALUES (
                        CAST(:id AS UUID), CAST(:job_id AS UUID), :stage, '1.0.0', 'running', 1,
                        CAST(:metrics AS JSONB), :started_at, NULL, :created_at
                    )
                    """
                ),
                {
                    "id": str(uuid.uuid4()),
                    "job_id": job_id,
                    "stage": stage,
                    "metrics": metrics,
                    "started_at": now,
                    "created_at": now,
                },
            )
    except Exception:
        logging.getLogger(__name__).exception(
            "could not record running stage %s for job %s", stage, job_id
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
    finished_at = datetime.utcnow()
    params = {
        "job_id": job_id,
        "stage": stage,
        "status": status,
        "outputs": json.dumps(outputs) if outputs else None,
        "metrics": json.dumps(metrics) if metrics else None,
        "started_at": started_at,
        "finished_at": finished_at,
        "error": json.dumps(error) if error else None,
        "created_at": started_at,
        "id": str(uuid.uuid4()),
    }
    with engine.begin() as conn:
        updated = conn.execute(
            text(
                """
                UPDATE job_steps
                SET status = :status,
                    finished_at = :finished_at,
                    output_uris = COALESCE(CAST(:outputs AS JSONB), output_uris),
                    metrics = COALESCE(CAST(:metrics AS JSONB), metrics),
                    error = CAST(:error AS JSONB)
                WHERE id = (
                    SELECT id FROM job_steps
                    WHERE job_id = CAST(:job_id AS UUID) AND stage = :stage
                    ORDER BY created_at DESC
                    LIMIT 1
                )
                """
            ),
            params,
        )
        if updated.rowcount:
            return
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
            params,
        )


def _finalize_media(
    output_dir: Path,
    input_path: Path,
    ingest_dict: Optional[dict],
    *,
    retention_policy: Optional[str],
    session_id: str,
) -> None:
    """Drop ephemeral transcodes and honor the user's retention choice."""
    from pipeline.retention import finalize_job_media

    media_root = Path(os.getenv("MEDIA_ROOT", "/data/stagecoach"))
    try:
        finalize_job_media(
            output_dir=output_dir,
            input_path=input_path,
            ingest_artifacts=(ingest_dict or {}).get("artifacts"),
            retention_policy=retention_policy,
            media_root=media_root if media_root.exists() else None,
            session_id=session_id,
        )
    except Exception:
        logging.getLogger(__name__).exception("retention finalize failed session=%s", session_id)


@app.task(name="tasks.health_check")
def health_check():
    """Health check task for worker verification."""
    return {"status": "healthy", "worker": "celery"}


@app.task(name="tasks.prep_llm")
def prep_llm_task(
    plan_id: str,
    section: str = "all",
    feedback: str = "",
    llm_settings: Optional[dict] = None,
) -> dict:
    """Build talk-prep outputs from the plan row. The local model is optional."""
    from pipeline.prep_llm import apply_prep_plan

    return apply_prep_plan(
        plan_id,
        section=section,
        feedback=feedback,
        llm_settings=llm_settings or {},
        use_llm=True,
    )


@app.task(name="tasks.retention_sweeper")
def retention_sweeper_task(now_iso: Optional[str] = None) -> dict:
    """Nightly cross-check of media_assets.retention_until (SPEC §10.3)."""
    from pipeline.retention import sweep_from_database

    now = datetime.fromisoformat(now_iso) if now_iso else datetime.utcnow()
    media_root = Path(os.getenv("MEDIA_ROOT", "/data/stagecoach"))
    result = sweep_from_database(now, media_root=media_root if media_root.exists() else None)
    logging.getLogger(__name__).info(
        "retention_sweeper object_count=%s kinds=%s",
        result.get("object_count"),
        result.get("kinds"),
    )
    return result


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


@app.task(name="tasks.vision", bind=True, max_retries=3)
def vision_task(
    self,
    ingest_result: dict,
    output_dir: str,
    session_id: str,
    consents: Optional[dict] = None,
    camera_setup: str = "unknown",
    accessibility_profile: Optional[dict] = None,
    job_id: Optional[str] = None,
):
    """Vision stage: CPU MediaPipe pose/hands/face (issue #38). Consent-gated."""
    from pipeline.accessibility import persist_accessibility
    from pipeline.consent import persist_consent_snapshot, run_vision_if_allowed
    from pipeline.stages.vision import run_vision_stage

    logger = logging.getLogger(__name__)
    dest = Path(output_dir)
    persist_accessibility(dest, accessibility_profile)
    snapshot = persist_consent_snapshot(dest, consents)
    artifacts = (ingest_result or {}).get("artifacts") or {}
    proxy = artifacts.get("analysis") or str(dest / "analysis.mp4")

    def runner(decision):
        return run_vision_stage(
            output_dir=dest,
            session_id=session_id,
            decision=decision,
            video_path=Path(proxy) if proxy else None,
            camera_setup=camera_setup,
        ).to_dict()

    if job_id:
        emit_progress(job_id, "vision", "running", pct=0, message="Tracking pose and face landmarks")
    try:
        from pipeline.partial import write_vision_status

        gate = run_vision_if_allowed(snapshot, runner)
        payload = gate.get("result") or gate
        status = "skipped" if gate["status"] == "skipped" or payload.get("skipped") else "succeeded"
        write_vision_status(dest, status, reason=gate.get("reason") or payload.get("skip_reason"))
        if job_id:
            emit_progress(job_id, "vision", status, pct=100, message="Vision stage finished")
        logger.info("vision task %s for %s", status, session_id)
        return payload
    except Exception as exc:
        from pipeline.partial import write_vision_status

        logger.error("vision failed for %s: %s", session_id, exc)
        write_vision_status(
            dest,
            "failed",
            error={"type": type(exc).__name__, "message": str(exc)[:200]},
        )
        if job_id:
            emit_progress(job_id, "vision", "failed", message=str(exc)[:200])
        if self.request.retries >= (self.max_retries or 0):
            return {"status": "failed", "error": str(exc)[:200]}
        raise self.retry(exc=exc, countdown=4 ** self.request.retries)


@app.task(name="tasks.slides", bind=True, max_retries=3)
def slides_task(
    self,
    output_dir: str,
    session_id: str,
    video_path: Optional[str] = None,
    deck_path: Optional[str] = None,
    camera_setup: str = "unknown",
    language: str = "en",
    is_screen_recording: bool = False,
    is_audio_only: bool = False,
    job_id: Optional[str] = None,
):
    """Slides stage: PySceneDetect, keyframes, deck text, OCR, matching (issue #43)."""
    from pipeline.stages.slides import run_slides_stage

    logger = logging.getLogger(__name__)
    dest = Path(output_dir)
    transcript = None
    tpath = dest / "transcript.json"
    if tpath.exists():
        try:
            transcript = json.loads(tpath.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            transcript = None
    if job_id:
        emit_progress(job_id, "slides", "running", pct=0, message="Detecting slides")
    try:
        result = run_slides_stage(
            output_dir=dest,
            session_id=session_id,
            video_path=Path(video_path) if video_path else None,
            deck_path=Path(deck_path) if deck_path else None,
            camera_setup=camera_setup,
            language=language,
            transcript=transcript,
            is_screen_recording=is_screen_recording,
            is_audio_only=is_audio_only,
        )
        status = "skipped" if result.skipped else "succeeded"
        if job_id:
            emit_progress(job_id, "slides", status, pct=100, message=result.skip_reason or "Slides ready")
        return result.to_dict()
    except Exception as exc:
        logger.error("slides failed for %s: %s", session_id, type(exc).__name__)
        if job_id:
            emit_progress(job_id, "slides", "failed", message=str(exc)[:200])
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
        from metrics.compute import persist_session_metrics

        dest = Path(output_dir)
        metrics_path = persist_session_metrics(
            output_dir=dest,
            transcript_path=transcript_path or dest / "transcript.json",
            audio_metrics_path=dest / "audio_metrics.json",
            pauses_path=dest / "pauses.json",
            packages_dir=Path("/packages"),
        )
        payload = result.to_dict()
        payload["artifacts"]["metrics"] = str(metrics_path)
        if job_id:
            emit_progress(
                job_id,
                "audio_features",
                "succeeded",
                pct=100,
                message="Prosody features extracted",
            )
        logger.info(f"audio_features completed for {session_id}")
        return payload
    except Exception as exc:
        logger.error(f"audio_features failed for {session_id}: {exc}")
        if job_id:
            emit_progress(job_id, "audio_features", "failed", message=f"audio_features failed: {str(exc)}")
        raise self.retry(exc=exc, countdown=4 ** self.request.retries)


def _write_export_meta(meta_path: Path, payload: dict) -> None:
    meta_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


@app.task(name="tasks.export_pdf", bind=True, max_retries=2)
def export_pdf_task(
    self,
    export_id: str,
    session_id: str,
    output_dir: str,
    dest_dir: str,
    include_transcript: bool = False,
):
    """SPEC §7.5 / §8.9 async PDF via Playwright Chromium (issue #49)."""
    from pipeline.pdf_export import export_session_pdf

    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    meta_path = dest / "meta.json"
    try:
        current = json.loads(meta_path.read_text()) if meta_path.is_file() else {}
        current.update({"id": export_id, "session_id": session_id, "status": "running"})
        _write_export_meta(meta_path, current)
        result = export_session_pdf(
            Path(output_dir),
            dest / "report.pdf",
            include_transcript=include_transcript,
        )
        current.update(
            {
                "status": "ready",
                "pdf": result["path"],
                "bytes": result["bytes"],
                "include_transcript": include_transcript,
            }
        )
        _write_export_meta(meta_path, current)
        return current
    except Exception as exc:
        current = json.loads(meta_path.read_text()) if meta_path.is_file() else {}
        current.update({"status": "failed", "error": str(exc)[:200]})
        _write_export_meta(meta_path, current)
        logger = logging.getLogger(__name__)
        logger.exception("export_pdf failed export=%s session=%s", export_id, session_id)
        raise


@app.task(name="tasks.fusion_scoring", bind=True, max_retries=3)
def fusion_scoring_task(
    self,
    audio_result: Optional[dict] = None,
    output_dir: str = "",
    session_id: str = "",
    context_type: str = "keynote",
    language: str = "en",
    slot_min: Optional[int] = None,
    job_id: Optional[str] = None,
):
    """Fusion + scoring from existing metrics / content artifacts (issue #30)."""
    from pipeline.stages.fusion_scoring import run_fusion_scoring

    logger = logging.getLogger(__name__)
    dest = Path(output_dir)
    if job_id:
        emit_progress(job_id, "fusion_scoring", "running", pct=0, message="Scoring measured signals")
    try:
        result = run_fusion_scoring(
            session_id=session_id,
            output_dir=dest,
            context_type=context_type,
            language=language,
            slot_min=slot_min,
            packages_dir=Path("/packages"),
        )
        if job_id:
            emit_progress(job_id, "fusion_scoring", "succeeded", pct=100, message="Scores ready")
        logger.info("fusion_scoring completed for %s", session_id)
        return result
    except Exception as exc:
        logger.error("fusion_scoring failed for %s: %s", session_id, exc)
        if job_id:
            emit_progress(job_id, "fusion_scoring", "failed", message=str(exc)[:200])
        raise self.retry(exc=exc, countdown=4 ** self.request.retries)


@app.task(name="tasks.report", bind=True, max_retries=3)
def report_task(
    self,
    fusion_result: Optional[dict] = None,
    output_dir: str = "",
    session_id: str = "",
    job_id: Optional[str] = None,
):
    """Report stage: facts-only coach text + report.json (issue #30)."""
    from pipeline.persist import persist_analysis_result
    from pipeline.stages.report import run_report_stage

    logger = logging.getLogger(__name__)
    dest = Path(output_dir)
    if job_id:
        emit_progress(job_id, "report", "running", pct=0, message="Writing report")
    try:
        report = run_report_stage(output_dir=dest, analysis=fusion_result, packages_dir=Path("/packages"))
        if job_id:
            persist_analysis_result(job_id=job_id, analysis=report)
            emit_progress(job_id, "report", "succeeded", pct=100, message="Report ready")
        logger.info("report completed for %s", session_id)
        return {"report_path": str(dest / "report.json"), "session_id": session_id}
    except Exception as exc:
        logger.error("report failed for %s: %s", session_id, exc)
        if job_id:
            emit_progress(job_id, "report", "failed", message=str(exc)[:200])
        raise self.retry(exc=exc, countdown=4 ** self.request.retries)


@app.task(name="tasks.prepare_session", bind=True, max_retries=1)
def prepare_session_task(
    self,
    *,
    job_id: str,
    session_id: str,
    input_path: str,
    output_dir: str,
    context_type: str,
    language: str,
    slot_min: Optional[int] = None,
    consents: Optional[dict] = None,
    camera_setup: str = "unknown",
    accessibility_profile: Optional[dict] = None,
    retention_policy: Optional[str] = None,
    llm_settings: Optional[dict] = None,
    qa_in_slot: bool = False,
    audience_desc: Optional[str] = None,
    delivery_mode: str = "webinar",
    source_kind: str = "upload",
):
    """Ingest + single-layout detection. Enqueue analysis or wait for review."""
    from pipeline.consent import decide_vision
    from pipeline.prepare import prepare_session

    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(__name__)
    _set_job_state(job_id, session_id, "preparing")
    started = datetime.utcnow()
    emit_progress(job_id, "ingest", "running", pct=5, message="Validating media", session_id=session_id)
    try:
        snapshot = consents or {}
        video_ok = bool(decide_vision(snapshot).run_pose)
        result = prepare_session(
            input_path=Path(input_path),
            output_dir=destination,
            session_id=session_id,
            delivery_mode=delivery_mode,
            video_analysis_consent=video_ok,
            layout_review_pref=_layout_review_pref(session_id),
            confirmed_layout_count=_confirmed_online_layouts(session_id),
        )
        ingest_dict = result["ingest"]
        _record_job_step(
            job_id=job_id,
            stage="ingest",
            status="succeeded",
            started_at=started,
            outputs=ingest_dict.get("artifacts"),
            metrics=ingest_dict.get("media_info"),
        )
        emit_progress(job_id, "ingest", "succeeded", pct=40, message="Media prepared", session_id=session_id)

        layout = result.get("layout")
        if result.get("skip_layout"):
            skip_reason = result.get("reason") or "audio_only_media"
            na_code = "consent_video_off" if skip_reason == "consent_video_off" else skip_reason
            skip_started = datetime.utcnow()
            for stage in ("layout", "layout_review", "region_crops"):
                _record_job_step(
                    job_id=job_id,
                    stage=stage,
                    status="skipped",
                    started_at=skip_started,
                    metrics={"reason": skip_reason, "na_code": na_code},
                )
                emit_progress(
                    job_id,
                    stage,
                    "skipped",
                    pct=80,
                    message=skip_reason,
                    session_id=session_id,
                )
        elif layout is not None:
            emit_progress(
                job_id,
                "layout",
                "running",
                pct=55,
                message="Looking for where your camera and your screen sit in the frame.",
                session_id=session_id,
            )
            layout_started = datetime.utcnow()
            _record_job_step(
                job_id=job_id,
                stage="layout",
                status="succeeded",
                started_at=layout_started,
                outputs={"layout": str(destination / "layout.json")},
                metrics={"confidence": layout.get("confidence"), "kind": (layout.get("segments") or [{}])[0].get("kind")},
            )
            emit_progress(job_id, "layout", "succeeded", pct=80, message="Layout ready", session_id=session_id)
            status = "auto_confirmed" if result.get("auto_confirmed") else "detected"
            layout["status"] = status
            (destination / "layout.json").write_text(json.dumps(layout, indent=2) + "\n")
            _persist_session_layout(session_id=session_id, job_id=job_id, layout=layout, status=status)

        analysis_kwargs = {
            "job_id": job_id,
            "session_id": session_id,
            "input_path": input_path,
            "output_dir": output_dir,
            "context_type": context_type,
            "language": language,
            "slot_min": slot_min,
            "consents": consents,
            "camera_setup": camera_setup,
            "accessibility_profile": accessibility_profile,
            "retention_policy": retention_policy,
            "llm_settings": llm_settings,
            "qa_in_slot": qa_in_slot,
            "audience_desc": audience_desc,
            "delivery_mode": delivery_mode,
            "source_kind": source_kind,
            "skip_ingest": True,
            "audio_only_chosen": bool(result.get("audio_only")),
        }
        if result["status"] == "layout_review":
            _set_job_state(job_id, session_id, "layout_review")
            emit_progress(
                job_id,
                "layout_review",
                "waiting",
                pct=90,
                message="Check the layout",
                session_id=session_id,
            )
            return {"job_id": job_id, "session_id": session_id, "status": "layout_review"}
        if not result.get("skip_layout"):
            emit_progress(
                job_id,
                "layout_review",
                "succeeded",
                pct=95,
                message="Layout confirmed automatically",
                session_id=session_id,
            )
        _enqueue_mvp_analysis(analysis_kwargs)
        return {"job_id": job_id, "session_id": session_id, "status": "processing"}
    except Exception as exc:
        safe_error = {"type": type(exc).__name__, "message": str(exc)[:500]}
        logger.exception("prepare_session failed session=%s job=%s", session_id, job_id)
        _set_job_state(job_id, session_id, "failed", safe_error)
        emit_progress(job_id, "ingest", "failed", message=str(exc)[:200], session_id=session_id)
        raise


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
    consents: Optional[dict] = None,
    camera_setup: str = "unknown",
    accessibility_profile: Optional[dict] = None,
    retention_policy: Optional[str] = None,
    llm_settings: Optional[dict] = None,
    qa_in_slot: bool = False,
    audience_desc: Optional[str] = None,
    delivery_mode: str = "stage",
    source_kind: str = "upload",
    skip_ingest: bool = False,
    layout_path: Optional[str] = None,
    analysis_window: Optional[dict] = None,
    audio_only_chosen: bool = False,
):
    """Run ingest → ASR → alignment → audio → partial scores → vision → slides → fusion → report."""
    from pipeline.accessibility import persist_accessibility
    from pipeline.consent import persist_consent_snapshot, run_vision_if_allowed
    from pipeline.partial import scored_category_ids, write_vision_status
    from pipeline.persist import persist_analysis_result
    from pipeline.stages.asr import transcribe_audio
    from pipeline.stages.audio_features import extract_audio_features
    from pipeline.stages.fusion_scoring import run_fusion_scoring
    from pipeline.stages.ingest import ingest
    from pipeline.stages.report import run_report_stage

    logger = logging.getLogger(__name__)
    source = Path(input_path)
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    _set_job_state(job_id, session_id, "running")
    ingest_dict = None

    try:
        persist_accessibility(destination, accessibility_profile)
        from llm.settings import persist_llm_settings

        persist_llm_settings(destination, llm_settings)
        os.environ["STAGECOACH_LLM_SETTINGS_PATH"] = str(destination / "llm_settings.json")
        snapshot = persist_consent_snapshot(destination, consents)
        vision_decision_early = run_vision_if_allowed(snapshot, runner=None)
        skip_vision_now = vision_decision_early["status"] == "skipped"
        if skip_vision_now:
            started = datetime.utcnow()
            emit_progress(
                job_id,
                "vision",
                "skipped",
                pct=0,
                message="Video analysis is off; pose and face landmarks were not processed",
            )
            write_vision_status(
                destination,
                "skipped",
                reason=vision_decision_early["reason"],
            )
            _record_job_step(
                job_id=job_id,
                stage="vision",
                status="skipped",
                started_at=started,
                metrics={
                    "reason": vision_decision_early["reason"],
                    "na_code": "consent_video_off",
                    "run_pose": False,
                    "run_expression_metrics": False,
                    "keep_raw_landmarks": False,
                },
            )

        started = datetime.utcnow()
        if skip_ingest:
            from pipeline.prepare import load_ingest_json

            ingest_dict = load_ingest_json(destination)
        else:
            emit_progress(job_id, "ingest", "running", pct=5, message="Validating media")
            ingest_result = ingest(source, destination, session_id)
            ingest_dict = ingest_result.to_dict()
            from pipeline.prepare import write_ingest_json

            write_ingest_json(destination, ingest_dict)
            _record_job_step(
                job_id=job_id,
                stage="ingest",
                status="succeeded",
                started_at=started,
                outputs=ingest_dict["artifacts"],
                metrics=ingest_dict["media_info"],
            )
            emit_progress(job_id, "ingest", "succeeded", pct=25, message="Media prepared")
        if audio_only_chosen:
            (destination / "analysis_flags.json").write_text(
                json.dumps({"audio_only_chosen": True}) + "\n"
            )

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

        from pipeline.stages.alignment_gate import run_live_alignment

        started = datetime.utcnow()
        emit_progress(job_id, "alignment", "running", pct=62, message="Aligning words to the audio")
        alignment = run_live_alignment(
            audio_path=Path(ingest_dict["artifacts"]["audio16k"]),
            transcript_path=transcript_path,
            output_dir=destination,
            session_id=session_id,
            language=transcript.language or language,
        )
        alignment_status = alignment["status"]
        _record_job_step(
            job_id=job_id,
            stage="alignment",
            status=alignment_status,
            started_at=started,
            outputs=alignment.get("artifacts"),
            metrics=alignment.get("metrics"),
            error=alignment.get("error") if alignment_status == "failed" else None,
        )
        emit_progress(
            job_id,
            "alignment",
            alignment_status,
            pct=64,
            message="Word timing aligned"
            if alignment_status == "succeeded"
            else "Word alignment is not available on this machine",
        )

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
        from metrics.compute import persist_session_metrics

        metrics_path = persist_session_metrics(
            output_dir=destination,
            transcript_path=transcript_path,
            audio_metrics_path=Path(audio.artifacts["audio_metrics"]),
            pauses_path=destination / "pauses.json",
            packages_dir=Path("/packages"),
            slot_s=(slot_min * 60) if slot_min else None,
        )
        audio.artifacts["metrics"] = str(metrics_path)
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
                "metrics_path": str(metrics_path),
            },
        )
        emit_progress(
            job_id,
            "audio_features",
            "succeeded",
            pct=80,
            message="Audio measurements ready",
        )

        if delivery_mode != "stage":
            from pipeline.stages.production_quality import run_production_quality

            pq_started = datetime.utcnow()
            emit_progress(job_id, "production_quality", "running", pct=80, message="Checking sound and picture")
            try:
                run_production_quality(
                    output_dir=destination,
                    media_path=source,
                    audio_metrics=audio.metrics,
                    source_height=((ingest_dict or {}).get("media_info") or {}).get("height"),
                )
                _record_job_step(
                    job_id=job_id,
                    stage="production_quality",
                    status="succeeded",
                    started_at=pq_started,
                    outputs={"production_quality": str(destination / "production_quality.json")},
                )
                emit_progress(job_id, "production_quality", "succeeded", pct=81, message="Sound and picture checked")
            except Exception as pq_exc:
                logger.exception("production_quality failed session=%s", session_id)
                _record_job_step(
                    job_id=job_id,
                    stage="production_quality",
                    status="failed",
                    started_at=pq_started,
                    error={"type": type(pq_exc).__name__, "message": str(pq_exc)[:200]},
                )
                emit_progress(job_id, "production_quality", "failed", message="Production quality skipped")

        started = datetime.utcnow()
        emit_progress(
            job_id,
            "partial_scoring",
            "running",
            pct=81,
            message="Scoring audio and text categories",
        )
        resolved_language = "pt-BR" if transcript.language.startswith("pt") else "en"
        analysis = run_fusion_scoring(
            session_id=session_id,
            output_dir=destination,
            context_type=context_type if context_type != "other" else "keynote",
            language=resolved_language,
            slot_min=slot_min,
            qa_in_slot=bool(qa_in_slot),
            camera_setup=camera_setup if camera_setup else "unknown",
            ingest=ingest_dict,
            transcript_path=transcript_path,
            audio_metrics_path=Path(audio.artifacts["audio_metrics"]),
            metrics_path=Path(audio.artifacts.get("metrics") or destination / "metrics.json"),
            content_path=destination / "content.json",
            packages_dir=Path("/packages"),
            delivery_mode=delivery_mode,
        )
        report = run_report_stage(
            output_dir=destination, analysis=analysis, packages_dir=Path("/packages")
        )
        persist_analysis_result(
            job_id=job_id,
            analysis=report,
            transcript=json.loads(transcript_path.read_text()),
        )
        report_path = destination / "report.json"
        playback = ingest_dict["artifacts"].get("playback") or str(source)
        live_categories = scored_category_ids(analysis)
        _record_job_step(
            job_id=job_id,
            stage="partial_scoring",
            status="succeeded",
            started_at=started,
            outputs={
                "report": str(report_path),
                "analysis_result": str(destination / "analysis_result.json"),
                "transcript": str(transcript_path),
                "playback": playback,
                "timeline": str(destination / "timeline.json"),
                "body": str(destination / "body.json"),
                "slides_tab": str(destination / "slides_tab.json"),
            },
            metrics={
                "categories": live_categories,
                "coverage": (analysis.get("overall") or {}).get("coverage"),
            },
        )
        emit_progress(
            job_id,
            "partial_scoring",
            "succeeded",
            pct=83,
            message="Audio and text scores ready",
        )
        emit_partial_ready(job_id, live_categories, session_id=session_id)

        if delivery_mode != "stage" and not audio_only_chosen:
            layout_file = Path(layout_path) if layout_path else destination / "layout.json"
            if layout_file.is_file():
                from pipeline.layout.crop import write_region_tracks

                crop_started = datetime.utcnow()
                emit_progress(job_id, "region_crops", "running", pct=83, message="Separating camera and screen")
                try:
                    layout_doc = json.loads(layout_file.read_text())
                    media = (ingest_dict or {}).get("media_info") or {}
                    write_region_tracks(
                        source,
                        destination,
                        layout_doc,
                        frame_width=int(media.get("width") or 1920),
                        frame_height=int(media.get("height") or 1080),
                    )
                    _record_job_step(
                        job_id=job_id,
                        stage="region_crops",
                        status="succeeded",
                        started_at=crop_started,
                        outputs={
                            "camera": str(destination / "camera.mp4") if (destination / "camera.mp4").is_file() else None,
                            "screen": str(destination / "screen.mp4") if (destination / "screen.mp4").is_file() else None,
                        },
                    )
                    emit_progress(job_id, "region_crops", "succeeded", pct=84, message="Camera and screen separated")
                except Exception as crop_exc:
                    logger.exception("region_crops failed session=%s", session_id)
                    _record_job_step(
                        job_id=job_id,
                        stage="region_crops",
                        status="failed",
                        started_at=crop_started,
                        error={"type": type(crop_exc).__name__, "message": str(crop_exc)[:200]},
                    )
                    emit_progress(job_id, "region_crops", "failed", message="Crops failed; using the full frame")

        if not skip_vision_now and not audio_only_chosen:
            from pipeline.consent import decide_vision
            from pipeline.stages.vision import run_vision_stage

            started = datetime.utcnow()
            emit_progress(
                job_id,
                "vision",
                "running",
                pct=84,
                message="Tracking pose and face landmarks",
            )
            try:

                def _vision_runner(decision):
                    camera = destination / "camera.mp4"
                    proxy = destination / "analysis.mp4"
                    vision_path = camera if camera.is_file() else (proxy if proxy.exists() else None)
                    setup = "to_camera" if camera.is_file() else camera_setup
                    return run_vision_stage(
                        output_dir=destination,
                        session_id=session_id,
                        decision=decision,
                        video_path=vision_path,
                        camera_setup=setup,
                    ).to_dict()

                vision_gate = run_vision_if_allowed(snapshot, _vision_runner)
                vision_result = vision_gate.get("result") or {}
                vision_status = (
                    "skipped"
                    if vision_result.get("skipped") or vision_gate["status"] == "skipped"
                    else "succeeded"
                )
                write_vision_status(
                    destination,
                    vision_status,
                    reason=vision_result.get("skip_reason") or vision_gate.get("reason"),
                )
                skip_reason = vision_result.get("skip_reason") or vision_gate.get("reason")
                vision_metrics = vision_result.get("metrics") or {
                    "reason": skip_reason,
                    "run_pose": decide_vision(snapshot).run_pose,
                }
                if vision_status == "skipped" and skip_reason:
                    vision_metrics = {**vision_metrics, "reason": skip_reason, "na_code": skip_reason}
                _record_job_step(
                    job_id=job_id,
                    stage="vision",
                    status=vision_status,
                    started_at=started,
                    outputs=vision_result.get("artifacts"),
                    metrics=vision_metrics,
                )
                emit_progress(
                    job_id,
                    "vision",
                    vision_status,
                    pct=86,
                    message="Vision aggregates ready"
                    if vision_status == "succeeded"
                    else "Vision skipped (no video stream)",
                )
            except Exception as vis_exc:
                logger.exception("vision failed session=%s; continuing audio/text", session_id)
                write_vision_status(
                    destination,
                    "failed",
                    error={"type": type(vis_exc).__name__, "message": str(vis_exc)[:200]},
                )
                _record_job_step(
                    job_id=job_id,
                    stage="vision",
                    status="failed",
                    started_at=started,
                    error={"type": type(vis_exc).__name__, "message": str(vis_exc)[:200]},
                )
                emit_progress(
                    job_id,
                    "vision",
                    "failed",
                    pct=86,
                    message="Vision failed; audio/text continue",
                )

        from pipeline.stages.slides import find_deck_path, run_slides_stage

        started = datetime.utcnow()
        emit_progress(job_id, "slides", "running", pct=84, message="Detecting slides")
        try:
            proxy = ingest_dict.get("artifacts", {}).get("analysis")
            modality = ingest_dict.get("modality") or {}
            screen = destination / "screen.mp4"
            slides_video = screen if screen.is_file() else (Path(proxy) if proxy else destination / "analysis.mp4")
            slides_out = run_slides_stage(
                output_dir=destination,
                session_id=session_id,
                video_path=slides_video,
                deck_path=find_deck_path(destination),
                camera_setup=camera_setup if camera_setup else "unknown",
                language=language,
                transcript=json.loads(transcript_path.read_text()) if transcript_path.exists() else None,
                is_screen_recording=bool(modality.get("is_screen_recording"))
                or camera_setup == "screen_recording"
                or screen.is_file(),
                is_audio_only=bool(modality.get("is_audio_only"))
                or camera_setup == "audio_only"
                or audio_only_chosen,
            )
            slides_status = "skipped" if slides_out.skipped else "succeeded"
            _record_job_step(
                job_id=job_id,
                stage="slides",
                status=slides_status,
                started_at=started,
                outputs=slides_out.artifacts,
                metrics=slides_out.metrics,
            )
            emit_progress(
                job_id,
                "slides",
                slides_status,
                pct=87,
                message=slides_out.skip_reason or "Slides ready",
            )
        except Exception as slides_exc:
            logger.exception("slides failed session=%s; continuing", session_id)
            _record_job_step(
                job_id=job_id,
                stage="slides",
                status="failed",
                started_at=started,
                error={"type": type(slides_exc).__name__, "message": str(slides_exc)[:200]},
            )
            emit_progress(job_id, "slides", "failed", pct=87, message="Slides failed; scoring continues")

        from pipeline.stages.content_llm import run_content_llm_safe

        started = datetime.utcnow()
        emit_progress(job_id, "content_llm", "running", pct=87, message="Reading the talk for content scores")
        duration_s = float(((ingest_dict or {}).get("media_info") or {}).get("duration") or 0) or 5400.0
        content_outcome = run_content_llm_safe(
            transcript_path=transcript_path,
            output_dir=destination,
            session_id=session_id,
            context_type=context_type if context_type != "other" else "keynote",
            language=resolved_language,
            audience_desc=audience_desc,
            max_duration_s=duration_s,
        )
        content_status = str(content_outcome.get("status") or "failed")
        _record_job_step(
            job_id=job_id,
            stage="content_llm",
            status="succeeded" if content_status == "succeeded" else content_status,
            started_at=started,
            outputs={"content": str(destination / "content.json")},
            metrics={
                "cost_usd": content_outcome.get("cost_usd"),
                "reason": content_outcome.get("reason"),
                "error_type": content_outcome.get("error_type"),
            },
        )
        emit_progress(
            job_id,
            "content_llm",
            "succeeded" if content_status == "succeeded" else "skipped",
            pct=88,
            message="Content scores ready"
            if content_status == "succeeded"
            else "Content analysis unavailable; those categories stay N/A",
        )

        started = datetime.utcnow()
        emit_progress(job_id, "fusion_scoring", "running", pct=90, message="Scoring from measured signals")
        analysis = run_fusion_scoring(
            session_id=session_id,
            output_dir=destination,
            context_type=context_type if context_type != "other" else "keynote",
            language=resolved_language,
            slot_min=slot_min,
            qa_in_slot=bool(qa_in_slot),
            camera_setup=camera_setup if camera_setup else "unknown",
            ingest=ingest_dict,
            transcript_path=transcript_path,
            audio_metrics_path=Path(audio.artifacts["audio_metrics"]),
            metrics_path=Path(audio.artifacts.get("metrics") or destination / "metrics.json"),
            content_path=destination / "content.json",
            packages_dir=Path("/packages"),
            delivery_mode=delivery_mode,
        )
        _record_job_step(
            job_id=job_id,
            stage="fusion_scoring",
            status="succeeded",
            started_at=started,
            outputs={"analysis_result": str(destination / "analysis_result.json")},
            metrics={"coverage": (analysis.get("overall") or {}).get("coverage")},
        )
        emit_progress(job_id, "fusion_scoring", "succeeded", pct=92, message="Scores computed")

        started = datetime.utcnow()
        emit_progress(job_id, "report", "running", pct=94, message="Building coaching report")
        report = run_report_stage(output_dir=destination, analysis=analysis, packages_dir=Path("/packages"))
        persist_analysis_result(
            job_id=job_id,
            analysis=report,
            transcript=json.loads(transcript_path.read_text()),
        )
        report_path = destination / "report.json"
        playback = ingest_dict["artifacts"].get("playback") or str(source)
        _record_job_step(
            job_id=job_id,
            stage="report",
            status="succeeded",
            started_at=started,
            outputs={
                "report": str(report_path),
                "analysis_result": str(destination / "analysis_result.json"),
                "transcript": str(transcript_path),
                "playback": playback,
                "timeline": str(destination / "timeline.json"),
                "body": str(destination / "body.json"),
                "slides_tab": str(destination / "slides_tab.json"),
            },
            metrics={
                "overall": (report.get("overall") or {}).get("score"),
                "confidence": (report.get("overall") or {}).get("confidence"),
                "partial": (report.get("overall") or {}).get("partial"),
            },
        )
        from pipeline.job_outcome import job_status_after_success

        terminal = job_status_after_success()
        _set_job_state(job_id, session_id, terminal)
        emit_progress(job_id, "report", "succeeded", pct=100, message="Report ready")
        emit_done(job_id, terminal, session_id=session_id)
        _finalize_media(
            destination,
            source,
            ingest_dict,
            retention_policy=retention_policy,
            session_id=session_id,
        )
        logger.info("MVP analysis completed session=%s job=%s", session_id, job_id)
        return {"job_id": job_id, "session_id": session_id, "report_path": str(report_path)}
    except Exception as exc:
        safe_error = {"type": type(exc).__name__, "message": str(exc)[:500]}
        logger.exception("MVP analysis failed session=%s job=%s", session_id, job_id)
        _set_job_state(job_id, session_id, "failed", safe_error)
        emit_progress(job_id, "pipeline", "failed", message="Analysis failed")
        if ingest_dict is not None:
            _finalize_media(
                destination,
                source,
                ingest_dict,
                retention_policy=retention_policy,
                session_id=session_id,
            )
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

