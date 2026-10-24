"""Public auth routes: password + Sign in with Apple (issue #68 / D9)."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.apple_oidc import apple_configured, authorize_url, exchange_code, pkce_pair
from app.database import get_db
from app.auth import get_authenticated_user
from app.identity_service import (
    change_password,
    consume_session_ticket,
    default_auth_store,
    finish_apple,
    forgot_password,
    login_user,
    register_user,
    reset_password,
    verify_email,
)
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])


class PasswordBody(BaseModel):
    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=1)


class TokenBody(BaseModel):
    token: str = Field(..., min_length=8)


class ResetBody(BaseModel):
    token: str = Field(..., min_length=8)
    password: str = Field(..., min_length=1)


class EmailBody(BaseModel):
    email: str = Field(..., min_length=3)


class TicketBody(BaseModel):
    ticket: str = Field(..., min_length=8)


class ChangePasswordBody(BaseModel):
    current_password: Optional[str] = None
    new_password: str = Field(..., min_length=1, max_length=200)
    confirm_password: str = Field(..., min_length=1, max_length=200)


class AppleStartBody(BaseModel):
    redirect_uri: str


class AppleFinishBody(BaseModel):
    id_token: Optional[str] = None
    nonce: str
    code: Optional[str] = None
    redirect_uri: Optional[str] = None
    verifier: Optional[str] = None


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip() or "unknown"
    if request.client:
        return request.client.host
    return "unknown"


@router.get("/apple/config")
def apple_config() -> dict[str, Any]:
    return {"enabled": apple_configured(), "provider": "apple"}


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(body: PasswordBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    return register_user(db, body.email, body.password)


@router.post("/login")
def login(body: PasswordBody, request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    return login_user(db, body.email, body.password, store=default_auth_store(), ip=_client_ip(request))


@router.post("/verify-email")
def verify(body: TokenBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    return verify_email(db, body.token)


@router.post("/forgot")
def forgot(body: EmailBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    return forgot_password(db, body.email)


@router.post("/reset")
def reset(body: ResetBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    return reset_password(db, body.token, body.password)


@router.post("/session-ticket")
def session_ticket(body: TicketBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    return consume_session_ticket(db, body.ticket)


@router.post("/password")
def password(
    body: ChangePasswordBody,
    request: Request,
    user: User = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Change the signed-in user's password. Allowed while must_change_password is set."""
    current = body.current_password.strip() if body.current_password else None
    return change_password(
        db,
        user,
        current_password=current or None,
        new_password=body.new_password,
        confirm_password=body.confirm_password,
        ip=_client_ip(request),
    )


@router.post("/apple/start")
def apple_start(body: AppleStartBody) -> dict[str, Any]:
    if not apple_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Sign in with Apple is not configured",
        )
    pair = pkce_pair()
    return {
        "enabled": True,
        **pair,
        "authorize_url": authorize_url(
            redirect_uri=body.redirect_uri,
            challenge=pair["challenge"],
            nonce=pair["nonce"],
            state=pair["state"],
        ),
    }


@router.post("/apple/finish")
def apple_finish(body: AppleFinishBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    id_token = body.id_token
    if not id_token and body.code and body.redirect_uri and body.verifier:
        if not apple_configured():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Sign in with Apple is not configured",
            )
        token_response = exchange_code(
            code=body.code,
            redirect_uri=body.redirect_uri,
            verifier=body.verifier,
            exchanger=_live_exchanger,
        )
        id_token = str(token_response.get("id_token") or "")
    if not id_token:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="id_token required")
    from app.apple_oidc import APPLE_JWKS

    jwks = _jwks_standin() or _fetch_jwks(APPLE_JWKS)
    return finish_apple(db, id_token=id_token, nonce=body.nonce, jwks=jwks)


def _live_exchanger(fields: dict[str, str]) -> dict[str, Any]:
    import json
    from urllib.parse import urlencode
    from urllib.request import Request, urlopen

    from app.apple_oidc import APPLE_TOKEN

    request = Request(
        APPLE_TOKEN,
        data=urlencode(fields).encode("utf-8"),
        method="POST",
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    with urlopen(request, timeout=10) as response:  # noqa: S310 — Apple token endpoint only
        return json.loads(response.read().decode("utf-8"))


def _fetch_jwks(url: str) -> dict[str, Any]:
    import json
    from urllib.request import urlopen

    with urlopen(url, timeout=10) as response:  # noqa: S310 — Apple JWKS only
        return json.loads(response.read().decode("utf-8"))


def _jwks_standin() -> dict[str, Any] | None:
    """Tests set APPLE_JWKS_JSON so CI never calls Apple."""
    import json
    import os

    raw = os.getenv("APPLE_JWKS_JSON")
    if not raw:
        return None
    return json.loads(raw)
