"""JWT verification for Auth.js tokens."""

import os
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User

security = HTTPBearer()

# Auth.js uses HS256 by default with AUTH_SECRET
AUTH_SECRET = os.getenv("AUTH_SECRET", "")
ALGORITHM = "HS256"


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Verify Auth.js JWT token.
    
    Returns:
        Decoded token payload
        
    Raises:
        HTTPException: 401 if token is invalid
    """
    try:
        token = credentials.credentials
        payload = jwt.decode(token, AUTH_SECRET, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
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
