"""Progress streaming endpoints - SSE for live pipeline updates.

Per issue #19: Stream progress events via Redis pub/sub to the client.
"""

import asyncio
import json
import logging
import os
from typing import AsyncGenerator

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models.analysis_job import AnalysisJob
from app.models.session import Session as SessionModel
from app.models.user import User

router = APIRouter(prefix="/sessions", tags=["progress"])
logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")


async def event_stream(job_id: str, timeout: int = 600) -> AsyncGenerator[str, None]:
    """
    Stream progress events from Redis pub/sub.
    
    Args:
        job_id: Analysis job ID
        timeout: Max seconds to keep stream open (default 10 minutes)
        
    Yields:
        SSE-formatted event strings
    """
    redis_client = await aioredis.from_url(REDIS_URL)
    pubsub = redis_client.pubsub()
    channel = f"progress:{job_id}"
    
    await pubsub.subscribe(channel)
    logger.info(f"Subscribed to {channel}")
    
    try:
        # Send initial keepalive
        yield f"data: {json.dumps({'type': 'connected', 'job_id': job_id})}\n\n"
        
        start_time = asyncio.get_event_loop().time()
        
        while True:
            # Check timeout
            if asyncio.get_event_loop().time() - start_time > timeout:
                logger.info(f"Stream timeout for {job_id}")
                break
            
            try:
                # Wait for message with short timeout to check for client disconnect
                message = await asyncio.wait_for(
                    pubsub.get_message(ignore_subscribe_messages=True),
                    timeout=1.0
                )
                
                if message and message["type"] == "message":
                    data = message["data"].decode("utf-8")
                    event = json.loads(data)
                    
                    # Send SSE event
                    yield f"data: {json.dumps(event)}\n\n"
                    logger.debug(f"Sent progress event: {event['status']}")
                    
                    # If stage succeeded or failed, check if pipeline is done
                    if event["status"] in ("succeeded", "failed"):
                        # Could check DB here if all stages done
                        pass
                        
            except asyncio.TimeoutError:
                # Send keepalive every second
                yield f": keepalive\n\n"
                continue
                
    except asyncio.CancelledError:
        logger.info(f"Stream cancelled for {job_id}")
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.close()
        await redis_client.close()
        logger.info(f"Unsubscribed from {channel}")


@router.get("/{session_id}/events")
async def stream_progress(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Stream live progress events for a session's analysis job via SSE.
    
    Per issue #19 acceptance criteria:
    - SSE endpoint streams {stage, status, pct, eta_s, message} events
    - Auth required
    - Handles reconnect (client should track last seen event)
    
    Returns:
        StreamingResponse with text/event-stream content type
    """
    # Verify session ownership
    session = db.query(SessionModel).filter(
        SessionModel.id == session_id,
        SessionModel.user_id == current_user.id
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    # Get active analysis job for this session
    job = db.query(AnalysisJob).filter(
        AnalysisJob.session_id == session_id
    ).order_by(AnalysisJob.created_at.desc()).first()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No analysis job found for this session"
        )
    
    logger.info(f"Starting SSE stream for job {job.id}")
    
    return StreamingResponse(
        event_stream(str(job.id)),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )
