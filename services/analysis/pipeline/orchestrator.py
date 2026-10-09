"""Pipeline orchestration for Stage Coach analysis

Per ADR-002 and issue #18: Celery DAG with job_steps, idempotency, retries.
"""

import hashlib
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

import redis
from celery import chain, group
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class StageStatus(str, Enum):
    """Stage execution status"""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class StageResult:
    """Result of a pipeline stage execution"""

    stage: str
    status: StageStatus
    output_uris: Optional[Dict[str, str]] = None
    error: Optional[Dict[str, Any]] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration_s: Optional[float] = None
    metrics: Dict[str, Any] = None


class PipelineOrchestrator:
    """
    Orchestrates the analysis pipeline DAG with Celery.

    Per issue #18 acceptance criteria:
    - Job steps tracked in DB with status transitions
    - Idempotency keys (session_id, stage, input_hash, stage_version)
    - Exponential backoff retries (3 attempts via task decorator)
    - Partial status: non-critical stage failures don't block the pipeline
    - Full reanalysis support
    """

    # Stage versions for idempotency
    STAGE_VERSIONS = {
        "ingest": "1.0.0",
        "asr": "1.0.0",
        "alignment": "1.0.0",
        "diarization": "1.0.0",
    }

    def __init__(self, celery_app, redis_url: str):
        self.app = celery_app
        self.redis = redis.from_url(redis_url)

    def compute_input_hash(self, stage: str, inputs: Dict[str, Any]) -> str:
        """Compute hash of stage inputs for idempotency."""
        hash_data = {
            "stage": stage,
            "inputs": inputs,
        }
        hash_json = json.dumps(hash_data, sort_keys=True)
        return hashlib.sha256(hash_json.encode()).hexdigest()

    def emit_progress(
        self,
        job_id: str,
        stage: str,
        status: str,
        pct: Optional[float] = None,
        eta_s: Optional[int] = None,
        message: Optional[str] = None,
    ):
        """
        Emit progress event to Redis pub/sub for SSE streaming (issue #19).
        
        Args:
            job_id: Analysis job ID
            stage: Pipeline stage name
            status: Status (pending, running, succeeded, failed)
            pct: Progress percentage (0-100)
            eta_s: Estimated seconds remaining
            message: Human-readable status message
        """
        event = {
            "stage": stage,
            "status": status,
            "pct": pct,
            "eta_s": eta_s,
            "message": message,
            "timestamp": datetime.utcnow().isoformat(),
        }
        channel = f"progress:{job_id}"
        self.redis.publish(channel, json.dumps(event))
        logger.info(f"Progress event published to {channel}: {event}")

    def build_pipeline(
        self,
        session_id: str,
        input_path: str,
        output_dir: str,
        language: Optional[str] = None,
    ):
        """
        Build Celery pipeline DAG for Phase 1 (ingest → ASR only).
        
        Returns a Celery chain that can be applied with .apply_async()
        """
        from worker import ingest_task, asr_task

        # Build simple chain: ingest → asr
        pipeline = chain(
            ingest_task.s(
                input_path=input_path,
                output_dir=output_dir,
                session_id=session_id,
            ),
            asr_task.s(
                output_dir=output_dir,
                session_id=session_id,
                language=language,
            ),
        )

        logger.info(f"Built pipeline for session {session_id}")
        return pipeline
