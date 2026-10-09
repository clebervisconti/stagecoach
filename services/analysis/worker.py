"""Celery worker for Stage Coach analysis pipeline.

Phase 0: Skeleton only.
Phase 1+: Pipeline stages implementation.
"""

import os
from celery import Celery

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
    task_routes={
        "tasks.ingest": {"queue": "cpu"},
        "tasks.asr": {"queue": "gpu"},
        "tasks.audio_features": {"queue": "cpu"},
        "tasks.vision": {"queue": "gpu"},
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


# Phase 1+: Import pipeline stage tasks
# from pipeline.ingest import ingest_task
# from pipeline.asr import asr_task
# etc.
