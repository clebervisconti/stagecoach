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
        "tasks.alignment": {"queue": "cpu"},  # WhisperX alignment
        "tasks.diarization": {"queue": "cpu"},  # pyannote diarization
        "tasks.audio_features": {"queue": "cpu"},
        "tasks.vision": {"queue": "cpu"},
        "tasks.slides": {"queue": "cpu"},
        "tasks.content_llm": {"queue": "llm"},
        "tasks.fusion_scoring": {"queue": "cpu"},
        "tasks.report": {"queue": "cpu"},
        "tasks.run_mvp_analysis": {"queue": "cpu"},
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
):
    """Run ingest → ASR → audio → partial scores → vision → slides → fusion → report."""
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

    try:
        persist_accessibility(destination, accessibility_profile)
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
                    "run_pose": False,
                    "run_expression_metrics": False,
                    "keep_raw_landmarks": False,
                },
            )

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
            qa_in_slot=False,
            camera_setup=camera_setup if camera_setup else "unknown",
            ingest=ingest_dict,
            transcript_path=transcript_path,
            audio_metrics_path=Path(audio.artifacts["audio_metrics"]),
            metrics_path=Path(audio.artifacts.get("metrics") or destination / "metrics.json"),
            content_path=destination / "content.json",
            packages_dir=Path("/packages"),
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

        if not skip_vision_now:
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
                    proxy = destination / "analysis.mp4"
                    return run_vision_stage(
                        output_dir=destination,
                        session_id=session_id,
                        decision=decision,
                        video_path=proxy if proxy.exists() else None,
                        camera_setup=camera_setup,
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
                _record_job_step(
                    job_id=job_id,
                    stage="vision",
                    status=vision_status,
                    started_at=started,
                    outputs=vision_result.get("artifacts"),
                    metrics=vision_result.get("metrics")
                    or {
                        "reason": vision_result.get("skip_reason") or vision_gate.get("reason"),
                        "run_pose": decide_vision(snapshot).run_pose,
                    },
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
            slides_out = run_slides_stage(
                output_dir=destination,
                session_id=session_id,
                video_path=Path(proxy) if proxy else destination / "analysis.mp4",
                deck_path=find_deck_path(destination),
                camera_setup=camera_setup if camera_setup else "unknown",
                language=language,
                transcript=json.loads(transcript_path.read_text()) if transcript_path.exists() else None,
                is_screen_recording=bool(modality.get("is_screen_recording"))
                or camera_setup == "screen_recording",
                is_audio_only=bool(modality.get("is_audio_only")) or camera_setup == "audio_only",
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

        started = datetime.utcnow()
        emit_progress(job_id, "fusion_scoring", "running", pct=88, message="Scoring from measured signals")
        analysis = run_fusion_scoring(
            session_id=session_id,
            output_dir=destination,
            context_type=context_type if context_type != "other" else "keynote",
            language=resolved_language,
            slot_min=slot_min,
            qa_in_slot=False,
            camera_setup=camera_setup if camera_setup else "unknown",
            ingest=ingest_dict,
            transcript_path=transcript_path,
            audio_metrics_path=Path(audio.artifacts["audio_metrics"]),
            metrics_path=Path(audio.artifacts.get("metrics") or destination / "metrics.json"),
            content_path=destination / "content.json",
            packages_dir=Path("/packages"),
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
        _set_job_state(job_id, session_id, "partial")
        emit_progress(job_id, "report", "succeeded", pct=100, message="Report ready")
        emit_done(job_id, "partial", session_id=session_id)
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

