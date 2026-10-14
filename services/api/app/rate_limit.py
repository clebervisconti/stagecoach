"""Redis token-bucket rate limits (SPEC §7.5)."""

from __future__ import annotations

import logging
import os
import time
from typing import Optional, Protocol

import redis
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
USER_RATE_PER_SEC = float(os.getenv("RATE_LIMIT_USER_PER_SEC", "2"))
USER_BURST = float(os.getenv("RATE_LIMIT_USER_BURST", "60"))
IP_RATE_PER_SEC = float(os.getenv("RATE_LIMIT_IP_PER_SEC", "4"))
IP_BURST = float(os.getenv("RATE_LIMIT_IP_BURST", "120"))


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


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip() or "unknown"
    if request.client:
        return request.client.host
    return "unknown"


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
        auth = request.headers.get("authorization") or ""
        if auth.lower().startswith("bearer "):
            token = auth.split(" ", 1)[1][:32]
            allowed, retry = consume(
                store,
                f"rl:user:{token}",
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
