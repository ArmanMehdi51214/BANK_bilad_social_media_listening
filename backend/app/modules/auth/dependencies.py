from collections.abc import Callable

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.exceptions import ForbiddenException, UnauthorizedException
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise UnauthorizedException("Authentication credentials were not provided")

    try:
        payload = decode_access_token(credentials.credentials)
    except ValueError:
        raise UnauthorizedException("Invalid or expired token")

    user_id = payload.get("user_id")

    if not user_id:
        raise UnauthorizedException("Invalid token payload")

    user = db.query(User).filter(User.id == user_id).first()

    if not user or not user.is_active:
        raise UnauthorizedException("User is inactive or does not exist")

    return user


def require_roles(allowed_roles: list[str]) -> Callable:
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise ForbiddenException(
                message="You do not have permission to access this resource",
                details={
                    "required_roles": allowed_roles,
                    "current_role": current_user.role,
                },
            )

        return current_user

    return role_checker


def require_admin() -> Callable:
    return require_roles([UserRole.ADMIN.value])


def require_admin_or_analyst() -> Callable:
    return require_roles([UserRole.ADMIN.value, UserRole.ANALYST.value])


def require_authenticated_user() -> Callable:
    return get_current_user
