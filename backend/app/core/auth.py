from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status

from app.core import security
from app.core.config import settings
from app.models.user import User
from app.services.auth_service import (
    AuthService,
    AuthServiceError,
    InactiveUserError,
    UserNotFoundError,
)


async def get_current_user(
    access_token: Annotated[str | None, Cookie(alias=settings.AUTH_COOKIE_NAME)] = None,
) -> User:
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = security.decode_access_token(access_token)
        user_id = str(payload["sub"])
        return await AuthService().get_user(user_id)
    except (security.InvalidTokenError, UserNotFoundError, InactiveUserError, RuntimeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication session",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except AuthServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        ) from exc


async def require_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )
    return current_user
