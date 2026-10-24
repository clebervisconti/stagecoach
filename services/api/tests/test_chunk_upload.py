"""Chunked uploads: assembly, resume, authorization, and the 2 GiB ceiling."""

from __future__ import annotations

import hashlib
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "postgresql://stagecoach@127.0.0.1/stagecoach_test")

from app.auth import jwt as jwt_mod
from app.chunk_upload import (
    CHUNK_BYTES,
    PRODUCT_MAX_BYTES,
    UploadRejected,
    assemble_upload,
    create_store,
    declare_upload,
    resolve_max_upload_bytes,
    status_of,
    write_chunk,
)
from app.database import get_db
from app.deletion import CONTENT_KEYS
from app.main import app
from app.models.audit_log import AuditLog
from app.models.session import Session as SessionModel
from app.models.user import User
from app.rate_limit import MemoryStore
from app.routers import sessions as sessions_mod
from tests.memory_db import MemoryDB

SECRET = "a" * 32
REPO = Path(__file__).resolve().parents[3]
_CALLS: list[tuple[str, dict]] = []


def _user(db: MemoryDB, email: str = "owner@example.invalid", **overrides: object) -> User:
    user = User(
        email=email,
        locale="en",
        timezone="UTC",
        role=overrides.get("role", "member"),
        session_version=int(overrides.get("session_version", 1)),
        online_modes=bool(overrides.get("online_modes", True)),
        must_change_password=bool(overrides.get("must_change_password", False)),
        retention_policy="days_30",
        accessibility_profile={},
        llm_settings={},
        failed_logins=0,
        email_verified_at=datetime.utcnow(),
    )
    db.add(user)
    db.flush()
    return user


def _session(db: MemoryDB, user: User, **overrides: object) -> SessionModel:
    session = SessionModel(
        user_id=user.id,
        title="AI PT02 webinar",
        context_type="keynote",
        language="pt-BR",
        camera_setup="unknown",
        delivery_mode=overrides.get("delivery_mode", "webinar"),
        source_kind="upload",
        status=overrides.get("status", "created"),
        qa_in_slot=True,
    )
    db.add(session)
    db.flush()
    return session


def _bearer(user: User) -> dict[str, str]:
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "email": user.email,
            "sub": str(user.id),
            "sv": int(user.session_version or 1),
            "iss": "stagecoach-web",
            "aud": "stagecoach-api",
            "iat": now,
            "exp": now + timedelta(minutes=5),
        },
        SECRET,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def _declare(**overrides: object) -> dict:
    body = {
        "filename": "webinar.mp4",
        "content_type": "video/mp4",
        "size": 10,
        "max_bytes": PRODUCT_MAX_BYTES,
        "allowed_extensions": {".mp4"},
        "allowed_content_types": {"video/mp4", "application/octet-stream"},
        "chunk_bytes": 4,
    }
    body.update(overrides)
    return declare_upload(**body)


@pytest.fixture(autouse=True)
def _isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    _CALLS.clear()
    monkeypatch.setattr(jwt_mod, "AUTH_SECRET", SECRET)
    monkeypatch.setattr(sessions_mod, "MEDIA_ROOT", tmp_path.resolve())
    monkeypatch.setattr(sessions_mod, "_probe_duration_seconds", lambda _path: 30.0)
    monkeypatch.setattr(sessions_mod, "enqueue_analysis", lambda task, kwargs: _CALLS.append((task, kwargs)))
    monkeypatch.setattr("app.rate_limit.redis.from_url", lambda *_args, **_kwargs: MemoryStore())
    monkeypatch.setenv("ONLINE_MODES_ENABLED", "true")


@pytest.fixture
def api(tmp_path: Path):
    db = MemoryDB()

    def override():
        yield db

    app.dependency_overrides[get_db] = override
    with TestClient(app) as client:
        yield client, db, tmp_path
    app.dependency_overrides.clear()


def test_low_max_upload_bytes_cannot_shrink_the_product_limit():
    assert resolve_max_upload_bytes("83886080") == (PRODUCT_MAX_BYTES, 83886080)
    assert resolve_max_upload_bytes("") == (PRODUCT_MAX_BYTES, None)
    assert resolve_max_upload_bytes(None) == (PRODUCT_MAX_BYTES, None)
    assert resolve_max_upload_bytes(str(PRODUCT_MAX_BYTES + 5)) == (PRODUCT_MAX_BYTES + 5, None)
    with pytest.raises(ValueError):
        resolve_max_upload_bytes("0")


def test_an_819_mib_webinar_is_under_the_limit_and_chunks_stay_proxy_safe():
    meta = _declare(size=819 * 1024 * 1024, chunk_bytes=CHUNK_BYTES)
    assert meta["size"] == 819 * 1024 * 1024
    assert meta["chunk_bytes"] == 8 * 1024 * 1024
    assert CHUNK_BYTES < 100 * 1024 * 1024
    with pytest.raises(UploadRejected) as too_big:
        _declare(size=PRODUCT_MAX_BYTES + 1)
    assert too_big.value.status_code == 413
    assert too_big.value.code == "file_too_large"
    with pytest.raises(UploadRejected) as kind:
        _declare(filename="notes.exe")
    assert kind.value.status_code == 415
    assert kind.value.code == "unsupported_type"


def test_assembly_resumes_after_a_missing_chunk(tmp_path: Path):
    directory = tmp_path / "parts"
    create_store(directory, _declare(size=10, chunk_bytes=4))
    write_chunk(directory, 0, b"aaaa")
    write_chunk(directory, 2, b"cc")
    assert status_of(directory)["missing"] == [1]
    with pytest.raises(UploadRejected) as missing:
        assemble_upload(directory, tmp_path / "early.mp4")
    assert missing.value.code == "incomplete"
    assert not (tmp_path / "early.mp4").exists()
    assert write_chunk(directory, 1, b"bbbb")["missing"] == []
    assert write_chunk(directory, 1, b"bbbb")["complete"] is True
    with pytest.raises(UploadRejected) as conflict:
        write_chunk(directory, 1, b"BBBB")
    assert conflict.value.code == "chunk_conflict"
    assembled = assemble_upload(directory, tmp_path / "out.mp4")
    assert (tmp_path / "out.mp4").read_bytes() == b"aaaabbbbcc"
    assert assembled["sha256"] == hashlib.sha256(b"aaaabbbbcc").hexdigest()


def test_a_chunk_over_the_proxy_safe_cap_is_not_file_too_large(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("app.chunk_upload.MAX_CHUNK_BYTES", 8)
    directory = tmp_path / "parts"
    create_store(directory, _declare(size=4, chunk_bytes=4))
    with pytest.raises(UploadRejected) as exc:
        write_chunk(directory, 0, b"0123456789")
    assert exc.value.status_code == 413
    assert exc.value.code == "chunk_too_large"


def test_deploy_defaults_match_the_two_gib_product_limit():
    assert "MAX_UPLOAD_BYTES=2147483648" in (REPO / ".env.example").read_text()
    assert "83886080" not in (REPO / ".env.example").read_text()
    compose = (REPO / "docker-compose.prod.yml").read_text()
    script = (REPO / "deploy/stagecoach-run.sh").read_text()
    assert "MAX_UPLOAD_BYTES: ${MAX_UPLOAD_BYTES:-2147483648}" in compose
    assert 'MAX_UPLOAD_BYTES="${MAX_UPLOAD_BYTES:-2147483648}"' in script
    web = (REPO / "apps/web/lib/chunked-upload.ts").read_text()
    assert "8 * 1024 * 1024" in web
    migration = (REPO / "services/api/alembic/versions/20261024_1800_013_media_asset_bytes.py").read_text()
    assert 'revision = "013_media_bytes"' in migration
    assert 'down_revision = "012_roles_sessions"' in migration


def _open(client: TestClient, session: SessionModel, headers: dict[str, str], **overrides: object):
    body = {
        "filename": "webinar.mp4",
        "content_type": "video/mp4",
        "size": 4,
        "rights_attested": True,
    }
    body.update(overrides)
    return client.post(f"/api/v1/sessions/{session.id}/uploads", headers=headers, json=body)


def test_missing_and_bad_tokens_are_rejected_on_every_upload_route(api):
    client, db, _root = api
    user = _user(db)
    session = _session(db, user)
    upload = "b" * 32
    routes = [
        ("post", f"/api/v1/sessions/{session.id}/uploads", {"json": {"filename": "a.mp4", "size": 4, "rights_attested": True}}),
        ("get", f"/api/v1/sessions/{session.id}/uploads/{upload}", {}),
        ("put", f"/api/v1/sessions/{session.id}/uploads/{upload}/chunks/0", {"content": b"abcd"}),
        ("post", f"/api/v1/sessions/{session.id}/uploads/{upload}/complete", {}),
    ]
    for method, url, kwargs in routes:
        anonymous = getattr(client, method)(url, **kwargs)
        assert anonymous.status_code == 401
        forged = getattr(client, method)(url, headers={"Authorization": "Bearer not-a-token"}, **kwargs)
        assert forged.status_code == 401


def test_another_user_and_a_viewer_cannot_touch_the_upload(api):
    client, db, _root = api
    owner = _user(db, "owner@example.invalid")
    other = _user(db, "other@example.invalid")
    viewer = _user(db, "viewer@example.invalid", role="viewer")
    session = _session(db, owner)
    created = _open(client, session, _bearer(owner))
    assert created.status_code == 201
    upload_id = created.json()["upload_id"]
    chunk = f"/api/v1/sessions/{session.id}/uploads/{upload_id}/chunks/0"
    assert client.put(chunk, headers=_bearer(other), content=b"abcd").status_code == 404
    assert client.get(f"/api/v1/sessions/{session.id}/uploads/{upload_id}", headers=_bearer(other)).status_code == 404
    assert client.post(f"/api/v1/sessions/{session.id}/uploads/{upload_id}/complete", headers=_bearer(other)).status_code == 404
    owned = _session(db, viewer)
    denied = _open(client, owned, _bearer(viewer))
    assert denied.status_code == 403


def test_webinar_requires_rights_and_the_online_flag(api, monkeypatch: pytest.MonkeyPatch):
    client, db, root = api
    user = _user(db, online_modes=True)
    session = _session(db, user, delivery_mode="webinar")
    missing = _open(client, session, _bearer(user), rights_attested=False)
    assert missing.status_code == 400
    assert not (root / str(session.id) / "upload-parts").exists()
    monkeypatch.delenv("ONLINE_MODES_ENABLED", raising=False)
    hidden = _open(client, session, _bearer(user), rights_attested=True)
    assert hidden.status_code == 404


def test_owner_assembles_a_webinar_and_a_second_complete_does_not_enqueue_again(api):
    client, db, root = api
    user = _user(db)
    session = _session(db, user)
    created = _open(client, session, _bearer(user), size=4)
    assert created.status_code == 201
    body = created.json()
    assert body["chunk_bytes"] == CHUNK_BYTES
    assert body["missing"] == [0]
    upload_id = body["upload_id"]
    early = client.post(f"/api/v1/sessions/{session.id}/uploads/{upload_id}/complete", headers=_bearer(user))
    assert early.status_code == 409
    assert early.json()["code"] == "incomplete"
    stored = client.put(
        f"/api/v1/sessions/{session.id}/uploads/{upload_id}/chunks/0",
        headers=_bearer(user),
        content=b"abcd",
    )
    assert stored.status_code == 200
    assert stored.json()["complete"] is True
    done = client.post(f"/api/v1/sessions/{session.id}/uploads/{upload_id}/complete", headers=_bearer(user))
    assert done.status_code == 202
    assert done.json()["status"] == "preparing"
    saved = list((root / str(session.id) / "upload").iterdir())
    assert [path.read_bytes() for path in saved] == [b"abcd"]
    assert _CALLS[0][0] == "tasks.prepare_session"
    assert _CALLS[0][1]["input_path"] == str(saved[0])
    again = client.post(f"/api/v1/sessions/{session.id}/uploads/{upload_id}/complete", headers=_bearer(user))
    assert again.status_code == 202
    assert again.json()["already"] is True
    assert len(_CALLS) == 1
    audits = db.query(AuditLog).all()
    assert audits
    assert audits[0].action == "rights_attested"
    assert CONTENT_KEYS.isdisjoint(audits[0].details)
    assert "abcd" not in str(audits[0].details)


def test_declared_size_over_the_product_limit_is_413_before_any_byte_is_stored(api):
    client, db, root = api
    user = _user(db)
    session = _session(db, user, delivery_mode="stage")
    response = _open(client, session, _bearer(user), size=PRODUCT_MAX_BYTES + 1, rights_attested=False)
    assert response.status_code == 413
    assert response.json()["code"] == "file_too_large"
    assert not (root / str(session.id)).exists()


def test_a_bad_chunk_and_a_foreign_upload_id_do_not_assemble(api):
    client, db, _root = api
    user = _user(db)
    session = _session(db, user, delivery_mode="stage")
    created = _open(client, session, _bearer(user), rights_attested=False)
    upload_id = created.json()["upload_id"]
    short = client.put(
        f"/api/v1/sessions/{session.id}/uploads/{upload_id}/chunks/0",
        headers=_bearer(user),
        content=b"ab",
    )
    assert short.status_code == 400
    assert short.json()["code"] == "bad_chunk"
    escaped = client.put(
        f"/api/v1/sessions/{session.id}/uploads/not-a-valid-upload-id/chunks/0",
        headers=_bearer(user),
        content=b"abcd",
    )
    assert escaped.status_code == 400
    assert client.put(
        f"/api/v1/sessions/{session.id}/uploads/{'c' * 32}/chunks/0",
        headers=_bearer(user),
        content=b"abcd",
    ).status_code == 404


def test_legacy_single_shot_still_accepts_a_small_file_and_names_a_real_oversize(api, monkeypatch):
    client, db, root = api
    user = _user(db, online_modes=False)
    session = _session(db, user, delivery_mode="stage")
    uploaded = client.post(
        f"/api/v1/sessions/{session.id}/upload",
        headers=_bearer(user),
        files={"file": ("talk.mp4", b"abcd", "video/mp4")},
    )
    assert uploaded.status_code == 202
    assert uploaded.json()["status"] == "processing"
    assert list((root / str(session.id) / "upload").iterdir())[0].read_bytes() == b"abcd"
    monkeypatch.setattr(sessions_mod, "MAX_FILE_SIZE", 3)
    other = _session(db, user, delivery_mode="stage")
    too_big = client.post(
        f"/api/v1/sessions/{other.id}/upload",
        headers=_bearer(user),
        files={"file": ("talk.mp4", b"abcd", "video/mp4")},
    )
    assert too_big.status_code == 413
    assert too_big.json()["code"] == "file_too_large"
