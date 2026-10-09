"""Stage Coach API - Main FastAPI application."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime

from app.routers import users, sessions

app = FastAPI(
    title="Stage Coach API",
    description="Evidence-based presentation coaching platform",
    version="0.1.0",
)

# CORS middleware for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(users.router, prefix="/api/v1", tags=["users"])
app.include_router(sessions.router, prefix="/api/v1", tags=["sessions"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Stage Coach API",
        "version": "0.1.0",
        "phase": "0",
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
        "services": {
            "api": "up",
            # Phase 0: DB check would go here
        },
    }
