<<<<<<< HEAD
"""Authentication module for Stage Coach API."""

from app.auth.jwt import get_current_user, User

__all__ = ["get_current_user", "User"]
=======
"""Authentication utilities."""

from app.auth.jwt import get_current_user, verify_token

__all__ = ["get_current_user", "verify_token"]
>>>>>>> origin/main
