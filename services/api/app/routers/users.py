"""User endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import Optional

from app.auth import get_current_user
from app.database import get_db
from app.models.user import User

router = APIRouter(prefix="/me", tags=["users"])


class UserProfile(BaseModel):
    """User profile response."""
    id: str
    email: str
    name: Optional[str] = None
    locale: str = "en"
    timezone: str = "UTC"
    accessibility_profile: Optional[dict] = None


class UserProfileUpdate(BaseModel):
    """User profile update request."""
    name: Optional[str] = Field(None, max_length=255)
    locale: Optional[str] = Field(None, pattern="^(en|pt-BR)$")
    timezone: Optional[str] = Field(None, max_length=50)
    accessibility_profile: Optional[dict] = None


@router.get("", response_model=UserProfile)
async def get_me(current_user: User = Depends(get_current_user)):
    """Get current user profile.
    
    Returns:
        User profile
    """
    return UserProfile(
        id=str(current_user.id),
        email=current_user.email,
        name=current_user.name,
        locale=current_user.locale,
        timezone=current_user.timezone,
        accessibility_profile=current_user.accessibility_profile,
    )


@router.patch("", response_model=UserProfile)
async def update_me(
    update: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update current user profile.
    
    Args:
        update: Profile update data
        current_user: Authenticated user
        db: Database session
        
    Returns:
        Updated user profile
    """
    if update.name is not None:
        current_user.name = update.name
    if update.locale is not None:
        current_user.locale = update.locale
    if update.timezone is not None:
        current_user.timezone = update.timezone
    if update.accessibility_profile is not None:
        current_user.accessibility_profile = update.accessibility_profile
    
    db.commit()
    db.refresh(current_user)
    
    return UserProfile(
        id=str(current_user.id),
        email=current_user.email,
        name=current_user.name,
        locale=current_user.locale,
        timezone=current_user.timezone,
        accessibility_profile=current_user.accessibility_profile,
    )
