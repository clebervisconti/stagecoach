"""Redis token-bucket rate limits (SPEC §7.5)."""

from __future__ import annotations

import hashlib
import logging
import os
import re
import time
from typing import Optional, Protocol

import redis
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
# An open session page is one SSE stream, a session GET about every 12s, and a
# single burst of artifact reads when a step finishes. 8/s with a burst of 120
# covers two tabs landing a report together. The old 2/s burst of 60 was one
# shared bucket (see user_rate_key) and a busy tab emptied it for everyone.
USER_RATE_PER_SEC = float(os.getenv("RATE_LIMIT_USER_PER_SEC", "8"))
USER_BURST = float(os.getenv("RATE_LIMIT_USER_BURST", "120"))
# The IP bucket is the one a NAT still shares. 16/s and a burst of 240 lets a
# small office open reports at the same time without one address locking the rest.
IP_RATE_PER_SEC = float(os.getenv("RATE_LIMIT_IP_PER_SEC", "16"))
IP_BURST = float(os.getenv("RATE_LIMIT_IP_BURST", "240"))

_SESSION_ID = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
_SESSION_DOCUMENT = re.compile(rf"^/api/v1/sessions/{_SESSION_ID}$")
_SESSION_EVENTS = re.compile(rf"^/api/v1/sessions/{_SESSION_ID}/events$")


class TokenStore(Protocol):
    def hgetall(self, key: str) -> dict: ...
    def hset(self, key: str, mapping: dict) -> None: ...
    def expire(self, key: str, seconds: int) -> None: ...


def consume(
    store: TokenStore,
    key: str,
    *,
    rate_per_sec: float,
    burst: float,
    now: Optional[float] = None,
) -> tuple[bool, float]:
    """Take one token. Returns (allowed, retry_after_s)."""
    now = time.time() if now is None else now
    raw = store.hgetall(key) or {}
    decoded = {
        (k.decode() if isinstance(k, bytes) else k): (
            v.decode() if isinstance(v, bytes) else v
        )
        for k, v in raw.items()
    }
    tokens = float(decoded.get("tokens", burst))
    last = float(decoded.get("last", now))
    tokens = min(burst, tokens + max(0.0, now - last) * rate_per_sec)
    if tokens < 1.0:
        store.hset(key, mapping={"tokens": tokens, "last": now})
        store.expire(key, 180)
        wait = (1.0 - tokens) / rate_per_sec if rate_per_sec > 0 else 1.0
        return False, max(wait, 0.1)
    store.hset(key, mapping={"tokens": tokens - 1.0, "last": now})
    store.expire(key, 180)
    return True, 0.0


class MemoryStore:
    """In-memory store for unit tests."""

    def __init__(self) -> None:
        self._data: dict[str, dict[str, str]] = {}

    def hgetall(self, key: str) -> dict:
        return dict(self._data.get(key, {}))

    def hset(self, key: str, mapping: dict) -> None:
        self._data.setdefault(key, {}).update({str(k): str(v) for k, v in mapping.items()})

    def expire(self, key: str, seconds: int) -> None:
        return None

    def clear(self) -> None:
        self._data.clear()


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip() or "unknown"
    if request.client:
        return request.client.host
    return "unknown"


def verified_user_id(token: str) -> Optional[str]:
    """Subject of a verified API JWT. None when the token does not verify.

    The route still checks the session version and the user row. This only
    separates rate-limit buckets. A bad signature falls through to a hash of
    the whole token so unverified callers do not share one bucket either.
    """
    import jwt
    from jwt.exceptions import InvalidTokenError

    from app.auth.jwt import ALGORITHM, AUTH_SECRET, JWT_AUDIENCE, JWT_ISSUER

    if len(AUTH_SECRET) < 32 or not token:
        return None
    try:
        payload = jwt.decode(
            token,
            AUTH_SECRET,
            algorithms=[ALGORITHM],
            issuer=JWT_ISSUER,
            audience=JWT_AUDIENCE,
            options={"require": ["exp", "iat", "sub"]},
        )
    except InvalidTokenError:
        return None
    subject = payload.get("sub")
    if not isinstance(subject, str):
        return None
    subject = subject.strip()
    return subject or None


def user_rate_key(authorization: Optional[str]) -> Optional[str]:
    """Per-user bucket key. None when the request is unauthenticated.

    The first 32 characters of an HS256 JWT are the fixed header. Keying on
    that prefix put every signed-in user in one Redis bucket.
    """
    if not authorization:
        return None
    scheme, _, rest = authorization.partition(" ")
    if scheme.lower() != "bearer":
        return None
    token = rest.strip()
    if not token:
        return None
    user_id = verified_user_id(token)
    if user_id:
        return f"rl:user:{user_id}"
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return f"rl:user:token:{digest}"


def user_bucket_exempt(method: str, path: str) -> bool:
    """Reads an open session page makes that must not spend the user burst.

    The per-IP bucket still applies. Artifact reads, writes, and every other
    route stay on the user bucket.
    """
    if method.upper() not in {"GET", "HEAD"}:
        return False
    if path == "/api/v1/me":
        return True
    return bool(_SESSION_DOCUMENT.match(path) or _SESSION_EVENTS.match(path))


class TokenBucketMiddleware(BaseHTTPMiddleware):
    """Per-user and per-IP token buckets on /api/v1."""

    def __init__(self, app, store: Optional[TokenStore] = None):
        super().__init__(app)
        self.store = store

    def _store(self) -> TokenStore:
        if self.store is not None:
            return self.store
        return redis.from_url(REDIS_URL)

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if not path.startswith("/api/v1"):
            return await call_next(request)
        store = self._store()
        ip = _client_ip(request)
        allowed, retry = consume(
            store,
            f"rl:ip:{ip}",
            rate_per_sec=IP_RATE_PER_SEC,
            burst=IP_BURST,
        )
        if not allowed:
            return _too_many(retry)
        if user_bucket_exempt(request.method, path):
            return await call_next(request)
        key = user_rate_key(request.headers.get("authorization"))
        if key is None:
            return await call_next(request)
        allowed, retry = consume(
            store,
            key,
            rate_per_sec=USER_RATE_PER_SEC,
            burst=USER_BURST,
        )
        if not allowed:
            return _too_many(retry)
        return await call_next(request)


def _too_many(retry_after: float) -> JSONResponse:
    seconds = max(1, int(retry_after + 0.999))
    return JSONResponse(
        status_code=429,
        headers={"Retry-After": str(seconds), "Content-Type": "application/problem+json"},
        content={
            "type": "https://datatracker.ietf.org/doc/html/rfc9457#section-3",
            "title": "Too Many Requests",
            "status": 429,
            "detail": "Rate limit exceeded",
        },
    )
