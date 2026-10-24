"""JWT verification for Auth.js tokens."""

import os
from typing import Optional
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from jwt.exceptions import InvalidTokenError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User

security = HTTPBearer()
optional_security = HTTPBearer(auto_error=False)

# Auth.js uses HS256 by default with AUTH_SECRET
AUTH_SECRET = os.getenv("AUTH_SECRET", "")
ALGORITHM = "HS256"
JWT_ISSUER = os.getenv("JWT_ISSUER", "stagecoach-web")
JWT_AUDIENCE = os.getenv("JWT_AUDIENCE", "stagecoach-api")


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Verify Auth.js JWT token.
    
    Returns:
        Decoded token payload
        
    Raises:
        HTTPException: 401 if token is invalid
    """
    if len(AUTH_SECRET) < 32:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured",
        )
    try:
        token = credentials.credentials
        payload = jwt.decode(
            token,
            AUTH_SECRET,
            algorithms=[ALGORITHM],
            issuer=JWT_ISSUER,
            audience=JWT_AUDIENCE,
            options={"require": ["exp", "iat", "sub"]},
        )
        return payload
    except InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "type": "https://datatracker.ietf.org/doc/html/rfc9457",
                "title": "Unauthorized",
                "status": 401,
                "detail": "Invalid authentication credentials",
            },
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


_VIEWER_WRITE_ALLOW = {
    "/api/v1/me/export",
    "/api/v1/auth/password",
}
_PASSWORD_CHANGE = "/api/v1/auth/password"


def _unauthorized(detail: str = "Invalid authentication credentials") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={
            "type": "https://datatracker.ietf.org/doc/html/rfc9457",
            "title": "Unauthorized",
            "status": 401,
            "detail": detail,
        },
        headers={"WWW-Authenticate": "Bearer"},
    )


def _session_version(token_data: dict) -> int:
    try:
        return int(token_data.get("sv"))
    except (TypeError, ValueError):
        return -1


async def get_authenticated_user(
    request: Request,
    token_data: dict = Depends(verify_token),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the session user. Does not enforce must_change_password."""
    _ = request
    email = str(token_data.get("email") or "").strip().lower()
    if not email:
        raise _unauthorized("Invalid token: no email claim")
    user = db.query(User).filter(User.email == email, User.deleted_at.is_(None)).first()
    if user is None or user.disabled_at is not None:
        raise _unauthorized()
    if _session_version(token_data) != int(user.session_version or 1):
        raise _unauthorized()
    return user


def _path(request: Request) -> str:
    return request.url.path.rstrip("/") or "/"


async def get_current_user(
    request: Request,
    token_data: dict = Depends(verify_token),
    db: Session = Depends(get_db),
) -> User:
    """Authenticated user who is allowed to use the product.

    A must_change_password session can only call the password-change route.
    Viewers can read, and can export or change their own password, but cannot
    mutate the product.
    """
    user = await get_authenticated_user(request, token_data, db)
    path = _path(request)
    if user.must_change_password and path != _PASSWORD_CHANGE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Password change required")
    if (user.role or "member") == "viewer" and request.method not in {"GET", "HEAD", "OPTIONS"}:
        if path not in _VIEWER_WRITE_ALLOW:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Viewer accounts cannot change this resource",
            )
    return user


async def get_optional_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(optional_security),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Return the user when a bearer token is present; otherwise None."""
    if credentials is None:
        return None
    token_data = verify_token(credentials)
    return await get_current_user(request, token_data, db)
