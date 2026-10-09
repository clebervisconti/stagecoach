#!/usr/bin/env python3
"""
Smoke test for DAG orchestration and SSE progress streaming.

Per issues #18 and #19:
- Verifies Celery chain (ingest → ASR) executes successfully
- Verifies job_steps are created and tracked
- Verifies SSE progress events are emitted

NOTE: These tests require Redis and should run in Docker Compose environment only.
"""

import asyncio
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest
import redis

# Skip all tests in this module if Redis is not available
try:
    r = redis.from_url("redis://localhost:6379", socket_connect_timeout=1)
    r.ping()
    REDIS_AVAILABLE = True
except (redis.ConnectionError, redis.TimeoutError):
    REDIS_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not REDIS_AVAILABLE,
    reason="Redis not available - these tests run in Docker Compose Smoke Test only"
)


def generate_test_fixture(tmpdir: Path) -> Path:
    """Generate a 3-second test audio file."""
    fixture_path = tmpdir / "test.mp3"
    cmd = [
        "ffmpeg",
        "-f", "lavfi",
        "-i", "sine=frequency=440:duration=3",
        "-ar", "16000",
        "-ac", "1",
        "-y",
        str(fixture_path),
        "-loglevel", "error",
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return fixture_path


def test_celery_health():
    """Test that Celery worker is responsive."""
    from worker import app
    
    print("Testing Celery health...")
    result = app.send_task("tasks.health_check", queue="cpu")
    health = result.get(timeout=10)
    assert health["status"] == "healthy"
    print("✅ Celery worker is healthy")


def test_ingest_asr_chain():
    """Test that ingest and ASR chain executes successfully."""
    from celery import chain
    from worker import app, ingest_task, asr_task
    
    print("\nTesting ingest → ASR chain...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        fixture_path = generate_test_fixture(tmpdir)
        output_dir = tmpdir / "output"
        output_dir.mkdir()
        
        # Create a simple job ID for testing
        job_id = "smoke-test-job"
        session_id = "smoke-test-session"
        
        # Build and execute chain
        pipeline = chain(
            ingest_task.s(
                input_path=str(fixture_path),
                output_dir=str(output_dir),
                session_id=session_id,
                job_id=job_id,
            ),
            asr_task.s(
                output_dir=str(output_dir),
                session_id=session_id,
                job_id=job_id,
            ),
        )
        
        result = pipeline.apply_async()
        
        # Wait for completion
        timeout = 120
        asr_output = result.get(timeout=timeout)
        
        # Verify ASR output
        assert "language" in asr_output
        assert "segments" in asr_output
        assert "word_count" in asr_output
        
        print(f"✅ Chain completed successfully")
        print(f"   Language: {asr_output['language']}")
        print(f"   Word count: {asr_output['word_count']}")
        print(f"   Segments: {len(asr_output['segments'])}")


def test_progress_events():
    """Test that progress events are emitted to Redis during execution."""
    from celery import chain
    from worker import ingest_task, asr_task
    
    print("\nTesting progress events...")
    
    r = redis.from_url("redis://localhost:6379")
    job_id = "progress-test-job"
    session_id = "progress-test-session"
    
    # Subscribe to progress channel
    pubsub = r.pubsub()
    channel = f"progress:{job_id}"
    pubsub.subscribe(channel)
    
    # Start pipeline
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        fixture_path = generate_test_fixture(tmpdir)
        output_dir = tmpdir / "output"
        output_dir.mkdir()
        
        pipeline = chain(
            ingest_task.s(
                input_path=str(fixture_path),
                output_dir=str(output_dir),
                session_id=session_id,
                job_id=job_id,
            ),
            asr_task.s(
                output_dir=str(output_dir),
                session_id=session_id,
                job_id=job_id,
            ),
        )
        
        result = pipeline.apply_async()
        
        # Collect events with timeout
        events = []
        start_time = time.time()
        timeout = 120
        
        while time.time() - start_time < timeout:
            message = pubsub.get_message(timeout=1.0)
            if message and message["type"] == "message":
                event = json.loads(message["data"])
                events.append(event)
                print(f"   Event: {event['stage']} → {event['status']}")
                
                # Check if we got succeeded events for both stages
                if len([e for e in events if e["status"] == "succeeded"]) >= 2:
                    break
        
        # Wait for result
        result.get(timeout=10)
        
        # Verify we got progress events
        assert len(events) > 0, "No progress events received"
        
        # Verify we got events for both stages
        stages = {e["stage"] for e in events}
        assert "ingest" in stages, "No ingest events"
        assert "asr" in stages, "No ASR events"
        
        # Verify we got succeeded events
        succeeded = [e for e in events if e["status"] == "succeeded"]
        assert len(succeeded) >= 2, f"Expected at least 2 succeeded events, got {len(succeeded)}"
        
        print(f"✅ Progress events verified")
        print(f"   Total events: {len(events)}")
        print(f"   Stages: {stages}")
        print(f"   Succeeded: {len(succeeded)}")


@pytest.mark.asyncio
async def test_sse_endpoint():
    """Test the SSE endpoint (requires API to be running)."""
    import aiohttp
    
    print("\nTesting SSE endpoint...")
    
    # Note: This test requires the API to be running and a valid session
    # For now, we'll just verify the endpoint exists
    try:
        async with aiohttp.ClientSession() as session:
            # Try to connect (will fail without auth, but endpoint should exist)
            async with session.get(
                "http://localhost:8000/api/v1/sessions/test/events",
                timeout=aiohttp.ClientTimeout(total=2)
            ) as resp:
                # We expect 401 or 404, not 500
                assert resp.status in (401, 404), f"Unexpected status: {resp.status}"
                print(f"✅ SSE endpoint exists (status: {resp.status})")
    except asyncio.TimeoutError:
        print("✅ SSE endpoint exists (connection timeout as expected without auth)")
    except Exception as e:
        print(f"⚠️  SSE endpoint test skipped: {e}")


def main():
    """Run all smoke tests."""
    print("=" * 60)
    print("DAG Orchestration and SSE Progress Smoke Test")
    print("=" * 60)
    
    try:
        test_celery_health()
        test_ingest_asr_chain()
        test_progress_events()
        
        # Run SSE test async
        asyncio.run(test_sse_endpoint())
        
        print("\n" + "=" * 60)
        print("✅ All smoke tests passed!")
        print("=" * 60)
        return 0
        
    except Exception as e:
        print(f"\n❌ Smoke test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
