"""Stage Coach API - Main FastAPI application."""

from fastapi import FastAPI
from datetime import datetime
import os
import redis
from sqlalchemy import text

from app.rate_limit import TokenBucketMiddleware
from app.observability import MetricsMiddleware, error_tracking_status, init_api_otel, render_metrics
from app.routers import users, sessions, progress, evidence, exports, transparency, admin
from app.database import engine

init_api_otel()

app = FastAPI(
    title="Stage Coach API",
    description="Evidence-based presentation coaching platform",
    version="0.2.0",
)

app.add_middleware(TokenBucketMiddleware)
app.add_middleware(MetricsMiddleware)

# Include routers
app.include_router(users.router, prefix="/api/v1", tags=["users"])
app.include_router(sessions.router, prefix="/api/v1", tags=["sessions"])
app.include_router(progress.router, prefix="/api/v1", tags=["progress"])
app.include_router(evidence.router, prefix="/api/v1", tags=["evidence"])
app.include_router(exports.router, prefix="/api/v1", tags=["exports"])
app.include_router(transparency.router, prefix="/api/v1", tags=["transparency"])
app.include_router(admin.router, prefix="/api/v1", tags=["admin"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Stage Coach API",
        "version": "0.2.0",
        "phase": "mvp",
    }


@app.get("/metrics")
async def metrics():
    """Prometheus scrape. Labels are handler templates only (no PII)."""
    from fastapi.responses import Response

    body, content_type = render_metrics()
    return Response(content=body, media_type=content_type)


@app.get("/observability")
async def observability():
    return {
        "traces": bool(os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")),
        "metrics": "/metrics",
        "error_tracking": error_tracking_status(),
    }


@app.get("/health")
async def health():
    """Health check endpoint.
    
    Returns:
        Status and timestamp
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/ready")
async def ready():
    """Readiness verifies dependencies without exposing connection details."""
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379")).ping()
    return {"status": "ready", "version": app.version}
