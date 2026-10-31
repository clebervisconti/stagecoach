"""GET /screens reads the file and refuses another user's session."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "postgresql://stagecoach@127.0.0.1/stagecoach_test")

import jwt
import pytest
from fastapi.testclient import TestClient

from app.auth import jwt as jwt_mod
from app.database import get_db
from app.main import app
from app.models.analysis_job import AnalysisJob
from app.models.session import Session as TalkSession
from app.models.user import User
from app.rate_limit import MemoryStore
from app.routers.sessions import sign_playback
from tests.memory_db import MemoryDB

SECRET = "b" * 32


def _bearer(user: User) -> dict[str, str]:
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "email": user.email,
            "sub": str(user.id),
            "sv": user.session_version,
            "iss": "stagecoach-web",
            "aud": "stagecoach-api",
            "iat": now,
            "exp": now + timedelta(minutes=5),
        },
        SECRET,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setattr(jwt_mod, "AUTH_SECRET", SECRET)
    monkeypatch.setattr("app.rate_limit.redis.from_url", lambda *_args, **_kwargs: MemoryStore())
    monkeypatch.setattr("app.routers.sessions.MEDIA_ROOT", tmp_path)
    db = MemoryDB()

    def override():
        yield db

    app.dependency_overrides[get_db] = override
    with TestClient(app) as test_client:
        yield test_client, db, tmp_path
    app.dependency_overrides.clear()


def _seed(db: MemoryDB, email: str, title: str) -> tuple[User, TalkSession, AnalysisJob]:
    user = User(
        email=email,
        locale="en",
        timezone="UTC",
        password_hash="x",
        email_verified_at=datetime.utcnow(),
        role="member",
        session_version=1,
    )
    db.add(user)
    db.flush()
    session = TalkSession(
        user_id=user.id,
        title=title,
        context_type="keynote",
        language="en",
        camera_setup="screen_recording",
        delivery_mode="webinar",
        source_kind="upload",
        status="ready",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(session)
    db.flush()
    job = AnalysisJob(
        session_id=session.id,
        scoring_config_version="1.1.0",
        pipeline_version="1",
        status="succeeded",
        created_at=datetime.utcnow(),
    )
    db.add(job)
    db.flush()
    return user, session, job


def test_owner_reads_screen_flow_and_keyframe(client):
    test_client, db, root = client
    user, session, job = _seed(db, "owner@example.invalid", "Webinar")
    job_dir = root / str(session.id) / str(job.id)
    frames = job_dir / "screen_keyframes"
    frames.mkdir(parents=True)
    (frames / "scr_001.jpg").write_bytes(b"\xff\xd8\xff")
    document = {
        "version": "1.0.0",
        "delivery_mode": "webinar",
        "screen_visible_s": 12,
        "content_judgment": False,
        "segments": [
            {
                "id": "scr_001",
                "index": 1,
                "type": "SLIDE",
                "keyframe": "screen_keyframes/scr_001.jpg",
                "t_start": 0,
                "t_end": 12,
            }
        ],
        "events": [],
        "metrics": [],
        "quality": {"asr_dropped_words": 0},
    }
    (job_dir / "screen_flow.json").write_text(json.dumps(document), encoding="utf-8")
    response = test_client.get(f"/api/v1/sessions/{session.id}/screens", headers=_bearer(user))
    assert response.status_code == 200
    body = response.json()
    assert body["content_judgment"] is False
    assert "keyframe_url" in body["segments"][0]
    url = body["segments"][0]["keyframe_url"]
    frame = test_client.get(url, headers=_bearer(user))
    assert frame.status_code == 200
    assert frame.headers["cache-control"] == "private, no-store"
    assert frame.content.startswith(b"\xff\xd8")


def test_missing_measurement_is_not_measured(client):
    test_client, db, _root = client
    user, session, _job = _seed(db, "owner2@example.invalid", "Empty")
    response = test_client.get(f"/api/v1/sessions/{session.id}/screens", headers=_bearer(user))
    assert response.status_code == 404
    assert response.json() == {"reason": "not_measured"}


def test_other_user_cannot_read_screens(client):
    test_client, db, root = client
    _owner, session, job = _seed(db, "owner3@example.invalid", "Mine")
    other, _other_session, _other_job = _seed(db, "other@example.invalid", "Theirs")
    job_dir = root / str(session.id) / str(job.id)
    job_dir.mkdir(parents=True)
    (job_dir / "screen_flow.json").write_text("{}", encoding="utf-8")
    response = test_client.get(f"/api/v1/sessions/{session.id}/screens", headers=_bearer(other))
    assert response.status_code == 404
    assert response.json()["detail"] == "Session not found"


def test_bad_signature_and_path_escape(client):
    test_client, db, root = client
    user, session, job = _seed(db, "owner4@example.invalid", "Signed")
    job_dir = root / str(session.id) / str(job.id)
    job_dir.mkdir(parents=True)
    secret = root / "secret.txt"
    secret.write_text("nope", encoding="utf-8")
    (job_dir / "screen_flow.json").write_text(
        json.dumps(
            {
                "version": "1.0.0",
                "segments": [{"index": 1, "keyframe": "../../secret.txt"}],
            }
        ),
        encoding="utf-8",
    )
    expires = int(datetime.now(timezone.utc).timestamp()) + 60
    bad = test_client.get(
        f"/api/v1/sessions/{session.id}/screens/keyframe/1?exp={expires}&sig=deadbeef",
        headers=_bearer(user),
    )
    assert bad.status_code == 403
    signature = sign_playback(f"{session.id}:screen:1", expires)
    escaped = test_client.get(
        f"/api/v1/sessions/{session.id}/screens/keyframe/1?exp={expires}&sig={signature}",
        headers=_bearer(user),
    )
    assert escaped.status_code == 404
    assert secret.read_text(encoding="utf-8") == "nope"
    assert b"nope" not in escaped.content
