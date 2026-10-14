"""JWT verification for Auth.js tokens."""

import os
from typing import Optional
from fastapi import Depends, HTTPException, status
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


async def get_current_user(
    token_data: dict = Depends(verify_token),
    db: Session = Depends(get_db)
) -> User:
    """Get current authenticated user from JWT.
    
    Args:
        token_data: Decoded JWT payload
        db: Database session
        
    Returns:
        User model
        
    Raises:
        HTTPException: 401 if user not found
    """
    email = token_data.get("email")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "type": "https://datatracker.ietf.org/doc/html/rfc9457",
                "title": "Unauthorized",
                "status": 401,
                "detail": "Invalid token: no email claim",
            },
        )
    
    user = db.query(User).filter(User.email == email, User.deleted_at.is_(None)).first()
    if not user:
        # Create user on first sign-in (Auth.js behavior)
        user = User(email=email)
        db.add(user)
        db.commit()
        db.refresh(user)
    
    return user


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(optional_security),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Return the user when a bearer token is present; otherwise None."""
    if credentials is None:
        return None
    token_data = verify_token(credentials)
    return await get_current_user(token_data, db)
