"""A file over 100 MB uploads through a proxy that rejects larger bodies.

The proxy stands in for Cloudflare's per-request cap (100 MB on Free and Pro).
One body over that cap is refused before it reaches the API. The same file,
split into 8 MiB chunks, is assembled and hashed.
"""

from __future__ import annotations

import hashlib
import json
import os
import socket
import socketserver
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
import pytest
import uvicorn

os.environ.setdefault("DATABASE_URL", "postgresql://stagecoach@127.0.0.1/stagecoach_test")

from app.auth import jwt as jwt_mod
from app.chunk_upload import CHUNK_BYTES
from app.database import get_db
from app.main import app
from app.models.session import Session as SessionModel
from app.models.user import User
from app.rate_limit import MemoryStore
from app.routers import sessions as sessions_mod
from tests.memory_db import MemoryDB

SECRET = "c" * 32
CAP = 100 * 1024 * 1024
FILE_SIZE = CAP + 1


def _header(headers: dict[str, str], name: str) -> str | None:
    for key, value in headers.items():
        if key.lower() == name:
            return value
    return None


def _read_headers(conn: socket.socket) -> tuple[str, bytes] | None:
    """Read one request head. A client that connects and leaves is ignored."""
    buf = b""
    while b"\r\n\r\n" not in buf:
        block = conn.recv(4096)
        if not block:
            if not buf:
                return None
            raise ConnectionError("client closed before headers")
        buf += block
        if len(buf) > 65536:
            raise ValueError("headers too large")
    head, rest = buf.split(b"\r\n\r\n", 1)
    return head.decode("iso-8859-1", "replace"), rest


def _read_exact(conn: socket.socket, size: int, prefetched: bytes) -> bytes:
    buf = bytearray(prefetched)
    while len(buf) < size:
        block = conn.recv(min(65536, size - len(buf)))
        if not block:
            break
        buf.extend(block)
    return bytes(buf)


def _read_response(conn: socket.socket) -> bytes:
    """Read one HTTP response. A missing Content-Length is read until the socket closes."""
    buf = bytearray()
    while b"\r\n\r\n" not in buf:
        block = conn.recv(65536)
        if not block:
            return bytes(buf)
        buf.extend(block)
    head, _, rest = bytes(buf).partition(b"\r\n\r\n")
    length: int | None = None
    for line in head.decode("iso-8859-1", "replace").split("\r\n")[1:]:
        if line.lower().startswith("content-length:"):
            length = int(line.split(":", 1)[1].strip())
    body = bytearray(rest)
    if length is None:
        while True:
            block = conn.recv(65536)
            if not block:
                break
            body.extend(block)
        return head + b"\r\n\r\n" + bytes(body)
    while len(body) < length:
        block = conn.recv(min(65536, length - len(body)))
        if not block:
            break
        body.extend(block)
    return head + b"\r\n\r\n" + bytes(body[:length])


def _chunk_index(target: str) -> str | None:
    path = target.split("?", 1)[0]
    marker = "/chunks/"
    if marker not in path:
        return None
    return path.split(marker, 1)[1].split("/", 1)[0]


class _Proxy(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, upstream: tuple[str, int], cap: int) -> None:
        super().__init__(("127.0.0.1", 0), _Handler)
        self.upstream = upstream
        self.cap = cap
        self.rejected = 0
        self.forwarded: list[int] = []
        self.forced_failures = 0
        self.fail_once: str | None = "1"
        self.error: BaseException | None = None


class _Handler(socketserver.BaseRequestHandler):
    server: _Proxy

    def handle(self) -> None:
        conn = self.request
        conn.settimeout(60)
        try:
            read = _read_headers(conn)
            if read is None:
                return
            head, prefetched = read
            lines = head.split("\r\n")
            method, target, _version = lines[0].split(" ", 2)
            headers: dict[str, str] = {}
            for line in lines[1:]:
                if ":" not in line:
                    continue
                key, value = line.split(":", 1)
                headers[key.strip()] = value.strip()
            length = int(_header(headers, "content-length") or "0")
            if length > self.server.cap:
                self.server.rejected += 1
                message = b'{"detail":"payload too large","code":"proxy_rejected"}'
                conn.sendall(
                    b"HTTP/1.1 413 Payload Too Large\r\n"
                    b"Content-Type: application/json\r\n"
                    b"Content-Length: " + str(len(message)).encode() + b"\r\n"
                    b"Connection: close\r\n\r\n" + message
                )
                return
            body = _read_exact(conn, length, prefetched)
            if self.server.fail_once is not None and _chunk_index(target) == self.server.fail_once:
                self.server.fail_once = None
                self.server.forced_failures += 1
                message = b'{"detail":"forced failure"}'
                conn.sendall(
                    b"HTTP/1.1 502 Bad Gateway\r\n"
                    b"Content-Type: application/json\r\n"
                    b"Content-Length: " + str(len(message)).encode() + b"\r\n"
                    b"Connection: close\r\n\r\n" + message
                )
                return
            self.server.forwarded.append(length)
            response = self._forward(method, target, headers, body)
            if not response.startswith(b"HTTP/"):
                raise ConnectionError(f"upstream sent {response[:120]!r}")
            conn.sendall(response)
        except Exception as exc:
            self.server.error = exc
            return

    def _forward(self, method: str, target: str, headers: dict[str, str], body: bytes) -> bytes:
        host, port = self.server.upstream
        upstream = socket.create_connection((host, port), timeout=60)
        try:
            upstream.settimeout(60)
            lines = [f"{method} {target} HTTP/1.1", f"Host: {host}:{port}", "Connection: close"]
            for key, value in headers.items():
                if key.lower() in {"host", "connection", "keep-alive", "content-length", "transfer-encoding"}:
                    continue
                lines.append(f"{key}: {value}")
            lines.append(f"Content-Length: {len(body)}")
            upstream.sendall(("\r\n".join(lines) + "\r\n\r\n").encode("iso-8859-1") + body)
            return _read_response(upstream)
        finally:
            upstream.close()


def _free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return int(port)


def _wait(port: int) -> None:
    deadline = time.time() + 10
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return
        except OSError:
            time.sleep(0.05)
    raise RuntimeError(f"127.0.0.1:{port} did not accept connections")


class _Api(threading.Thread):
    def __init__(self, port: int) -> None:
        super().__init__(daemon=True)
        self.error: BaseException | None = None
        config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", access_log=False)
        self.server = uvicorn.Server(config)
        self.server.install_signal_handlers = lambda: None  # type: ignore[method-assign]

    def run(self) -> None:
        try:
            self.server.run()
        except BaseException as exc:  # pragma: no cover - surfaced by the test
            self.error = exc


def _user(db: MemoryDB) -> User:
    user = User(
        email="owner@example.invalid",
        locale="pt-BR",
        timezone="UTC",
        role="admin",
        session_version=1,
        online_modes=True,
        must_change_password=False,
        retention_policy="days_30",
        accessibility_profile={},
        llm_settings={},
        failed_logins=0,
        email_verified_at=datetime.utcnow(),
    )
    db.add(user)
    db.flush()
    return user


def _bearer(user: User) -> dict[str, str]:
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "email": user.email,
            "sub": str(user.id),
            "sv": 1,
            "iss": "stagecoach-web",
            "aud": "stagecoach-api",
            "iat": now,
            "exp": now + timedelta(minutes=10),
        },
        SECRET,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def _request(method: str, url: str, body: bytes | None, headers: dict[str, str]) -> tuple[int, bytes]:
    request = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def _exchange(method: str, url: str, body: bytes | None, headers: dict[str, str]) -> tuple[int, bytes]:
    last = (0, b"")
    for _attempt in range(4):
        try:
            status, payload = _request(method, url, body, headers)
        except urllib.error.URLError:
            time.sleep(0.05)
            continue
        last = (status, payload)
        if 200 <= status < 300:
            return last
        if status >= 500 or status in {408, 429}:
            time.sleep(0.05)
            continue
        return last
    return last


def _write_source(path: Path, size: int) -> str:
    digest = hashlib.sha256()
    block = b"stagecoach-webinar" * 4096
    remaining = size
    with path.open("wb") as handle:
        while remaining:
            piece = block if remaining >= len(block) else block[:remaining]
            handle.write(piece)
            digest.update(piece)
            remaining -= len(piece)
    return digest.hexdigest()


def _slice(path: Path, start: int, end: int) -> bytes:
    with path.open("rb") as handle:
        handle.seek(start)
        return handle.read(end - start)


def test_file_over_100mb_uploads_through_a_100mb_proxy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    calls: list[tuple[str, dict]] = []
    monkeypatch.setattr(jwt_mod, "AUTH_SECRET", SECRET)
    monkeypatch.setattr(sessions_mod, "MEDIA_ROOT", tmp_path.resolve())
    monkeypatch.setattr(sessions_mod, "_probe_duration_seconds", lambda _path: 35 * 60)
    monkeypatch.setattr(sessions_mod, "enqueue_analysis", lambda task, kwargs: calls.append((task, kwargs)))
    monkeypatch.setattr("app.rate_limit.redis.from_url", lambda *_args, **_kwargs: MemoryStore())
    monkeypatch.setenv("ONLINE_MODES_ENABLED", "true")

    db = MemoryDB()

    def override():
        yield db

    # Included routers under a live uvicorn server do not reliably apply
    # dependency_overrides. get_db() resolves SessionLocal when the request
    # runs, so the same MemoryDB is what either path yields.
    app.dependency_overrides[get_db] = override
    monkeypatch.setattr("app.database.SessionLocal", lambda: db)
    user = _user(db)
    session = SessionModel(
        user_id=user.id,
        title="AI PT02 webinar (Splunk) – full recording",
        context_type="keynote",
        language="pt-BR",
        camera_setup="unknown",
        delivery_mode="webinar",
        source_kind="upload",
        status="created",
        qa_in_slot=True,
    )
    db.add(session)
    db.flush()
    headers = _bearer(user)

    api_port = _free_port()
    api = _Api(api_port)
    api.start()
    proxy: _Proxy | None = None
    proxy_thread: threading.Thread | None = None
    try:
        _wait(api_port)
        proxy = _Proxy(("127.0.0.1", api_port), CAP)
        proxy_thread = threading.Thread(target=proxy.serve_forever, daemon=True)
        proxy_thread.start()
        proxy_port = proxy.server_address[1]
        _wait(proxy_port)
        base = f"http://127.0.0.1:{proxy_port}/api/v1/sessions/{session.id}"

        probe = socket.create_connection(("127.0.0.1", proxy_port), timeout=5)
        try:
            probe.sendall(
                (
                    f"POST /api/v1/sessions/{session.id}/upload HTTP/1.1\r\n"
                    f"Host: 127.0.0.1:{proxy_port}\r\n"
                    f"Content-Type: video/mp4\r\n"
                    f"Content-Length: {FILE_SIZE}\r\n"
                    f"Authorization: {headers['Authorization']}\r\n"
                    "Connection: close\r\n\r\n"
                ).encode()
            )
            probe.settimeout(5)
            status_line = b""
            while b"\r\n" not in status_line:
                block = probe.recv(4096)
                if not block:
                    break
                status_line += block
        finally:
            probe.close()
        assert b" 413 " in status_line.split(b"\r\n", 1)[0]
        assert proxy.rejected == 1
        assert proxy.forwarded == []
        assert not (tmp_path / str(session.id) / "upload").exists()

        source = tmp_path / "source.mp4"
        digest = _write_source(source, FILE_SIZE)
        created_status, created_body = _exchange(
            "POST",
            f"{base}/uploads",
            json.dumps(
                {
                    "filename": "webinar.mp4",
                    "content_type": "video/mp4",
                    "size": FILE_SIZE,
                    "rights_attested": True,
                }
            ).encode(),
            {**headers, "Content-Type": "application/json"},
        )
        assert created_status == 201, (created_body, proxy.error)
        opened = json.loads(created_body)
        upload_id = opened["upload_id"]
        chunk_bytes = int(opened["chunk_bytes"])
        assert chunk_bytes == CHUNK_BYTES
        missing = list(opened["missing"])
        assert missing
        for index in missing:
            start = index * chunk_bytes
            piece = _slice(source, start, min(FILE_SIZE, start + chunk_bytes))
            assert len(piece) <= CHUNK_BYTES
            status, payload = _exchange(
                "PUT",
                f"{base}/uploads/{upload_id}/chunks/{index}",
                piece,
                {**headers, "Content-Type": "application/octet-stream"},
            )
            assert status == 200, payload
        done_status, done_body = _exchange("POST", f"{base}/uploads/{upload_id}/complete", b"", headers)
        assert done_status == 202, done_body
        assert json.loads(done_body)["status"] == "preparing"
        assert proxy.forced_failures == 1
        assert proxy.rejected == 1
        assert proxy.forwarded
        assert max(proxy.forwarded) <= CHUNK_BYTES
        assert FILE_SIZE > CAP
        saved = list((tmp_path / str(session.id) / "upload").iterdir())
        assert len(saved) == 1
        assert saved[0].stat().st_size == FILE_SIZE
        assert hashlib.sha256(saved[0].read_bytes()).hexdigest() == digest
        assert calls[0][0] == "tasks.prepare_session"
        assert calls[0][1]["language"] == "pt-BR"
        assert not list((tmp_path / str(session.id) / "upload-parts").rglob("*.part"))
        assert api.error is None
        assert proxy.error is None
    finally:
        app.dependency_overrides.clear()
        if proxy is not None:
            proxy.shutdown()
            proxy.server_close()
        if proxy_thread is not None:
            proxy_thread.join(timeout=5)
        api.server.should_exit = True
        api.join(timeout=5)
