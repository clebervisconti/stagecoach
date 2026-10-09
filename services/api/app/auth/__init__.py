"""Authentication module for Stage Coach API."""

from app.auth.jwt import get_current_user, User

__all__ = ["get_current_user", "User"]
