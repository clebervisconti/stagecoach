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

# Register routers
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
            # Phase 0: no DB/Redis checks yet
        },
    }


@app.get("/me")
async def get_me():
    """Get current user info (placeholder).
    
    Phase 0: returns mock data.
    Phase 1+: requires authentication.
    """
    return {
        "id": "00000000-0000-0000-0000-000000000000",
        "email": "dev@example.com",
        "name": "Development User",
        "locale": "en",
    }
