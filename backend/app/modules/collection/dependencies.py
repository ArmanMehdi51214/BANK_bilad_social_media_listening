from __future__ import annotations

from fastapi import Depends, HTTPException, status

from app.models.user import User
from app.modules.auth.dependencies import get_current_user


ALLOWED_COLLECTION_ROLES = {"admin", "analyst"}


def require_collection_operator(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Allows only admin and analyst users to run live collection jobs.

    Business reason:
    Collection triggers paid external API usage and writes production intelligence data,
    so it must not be open to all users.
    """
    role = getattr(current_user, "role", "")
    role_value = getattr(role, "value", role)
    role_value = str(role_value).lower()

    if role_value not in ALLOWED_COLLECTION_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin and analyst users can run collection jobs.",
        )

    return current_user
