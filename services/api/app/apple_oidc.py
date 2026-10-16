"""Sign in with Apple: OIDC + PKCE + nonce. Disabled until secrets exist.

Tests inject JWKS / HTTP stand-ins. No live calls to appleid.apple.com in CI.
"""

from __future__ import annotations

import base64
import hashlib
import os
import secrets
import time
from typing import Any, Callable
from urllib.parse import urlencode

import jwt
from jwt import PyJWK

APPLE_ISSUER = "https://appleid.apple.com"
APPLE_AUTHORIZE = "https://appleid.apple.com/auth/authorize"
APPLE_TOKEN = "https://appleid.apple.com/auth/token"
APPLE_JWKS = "https://appleid.apple.com/auth/keys"
PRIVATE_RELAY_SUFFIX = "@privaterelay.appleid.com"

JwksFetcher = Callable[[], dict[str, Any]]
TokenExchanger = Callable[[dict[str, str]], dict[str, Any]]


def apple_configured() -> bool:
    return all(
        [
            os.getenv("APPLE_CLIENT_ID"),
            os.getenv("APPLE_TEAM_ID"),
            os.getenv("APPLE_KEY_ID"),
            os.getenv("APPLE_PRIVATE_KEY"),
        ]
    )


def _pem_private_key() -> str:
    raw = os.getenv("APPLE_PRIVATE_KEY") or ""
    return raw.replace("\\n", "\n")


def apple_client_secret(*, now: int | None = None) -> str:
    """ES256 client secret JWT (Apple's required assertion)."""
    issued = int(now if now is not None else time.time())
    payload = {
        "iss": os.environ["APPLE_TEAM_ID"],
        "iat": issued,
        "exp": issued + 86400 * 150,
        "aud": APPLE_ISSUER,
        "sub": os.environ["APPLE_CLIENT_ID"],
    }
    return jwt.encode(
        payload,
        _pem_private_key(),
        algorithm="ES256",
        headers={"kid": os.environ["APPLE_KEY_ID"], "alg": "ES256"},
    )


def pkce_pair() -> dict[str, str]:
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    nonce = secrets.token_urlsafe(32)
    state = secrets.token_urlsafe(24)
    return {"verifier": verifier, "challenge": challenge, "nonce": nonce, "state": state}


def authorize_url(*, redirect_uri: str, challenge: str, nonce: str, state: str) -> str:
    query = urlencode(
        {
            "client_id": os.environ["APPLE_CLIENT_ID"],
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "response_mode": "query",
            "scope": "name email",
            "state": state,
            "nonce": nonce,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
    )
    return f"{APPLE_AUTHORIZE}?{query}"


def is_private_relay(email: str | None) -> bool:
    return bool(email) and email.lower().endswith(PRIVATE_RELAY_SUFFIX)


def validate_id_token(
    id_token: str,
    *,
    nonce: str,
    audience: str | None = None,
    jwks: dict[str, Any],
) -> dict[str, Any]:
    header = jwt.get_unverified_header(id_token)
    kid = header.get("kid")
    matching = next((key for key in jwks.get("keys", []) if key.get("kid") == kid), None)
    if matching is None:
        raise ValueError("Unknown Apple signing key")
    payload = jwt.decode(
        id_token,
        key=PyJWK.from_dict(matching).key,
        algorithms=["RS256", "ES256"],
        audience=audience or os.environ["APPLE_CLIENT_ID"],
        issuer=APPLE_ISSUER,
        options={"require": ["exp", "iat", "sub"]},
    )
    if payload.get("nonce") != nonce:
        raise ValueError("nonce mismatch")
    email = payload.get("email")
    payload["private_relay"] = is_private_relay(email)
    return payload


def exchange_code(
    *,
    code: str,
    redirect_uri: str,
    verifier: str,
    exchanger: TokenExchanger | None = None,
) -> dict[str, Any]:
    if exchanger is None:
        raise RuntimeError("Live Apple token exchange is disabled in tests; inject an exchanger")
    return exchanger(
        {
            "client_id": os.environ["APPLE_CLIENT_ID"],
            "client_secret": apple_client_secret(),
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
            "code_verifier": verifier,
        }
    )
