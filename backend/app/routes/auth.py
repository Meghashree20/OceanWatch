from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.core import security
from app.core.auth import get_current_user
from app.core.config import settings
from app.models.user import User
from app.schemas.auth import AuthSessionResponse, LoginRequest, SignupRequest, UserResponse
from app.services.auth_service import (
    AuthService,
    DuplicateEmailError,
    InactiveUserError,
    InvalidCredentialsError,
)


router = APIRouter()


@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def signup(request: SignupRequest) -> UserResponse:
    try:
        user = await AuthService().register_user(
            full_name=request.full_name,
            email=str(request.email),
            password=request.password,
        )
    except DuplicateEmailError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is unavailable",
        ) from exc
    return UserResponse.model_validate(user)


@router.post("/login", response_model=AuthSessionResponse)
async def login(request: LoginRequest, response: Response) -> AuthSessionResponse:
    try:
        user = await AuthService().authenticate_user(
            email=str(request.email),
            password=request.password,
        )
    except (InvalidCredentialsError, InactiveUserError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is unavailable",
        ) from exc

    expires_in = settings.AUTH_ACCESS_TOKEN_EXPIRE_MINUTES * 60
    try:
        token = security.create_access_token(
            user.user_id,
            expires_delta=timedelta(seconds=expires_in),
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is unavailable",
        ) from exc
    response.set_cookie(
        key=settings.AUTH_COOKIE_NAME,
        value=token,
        max_age=expires_in,
        expires=expires_in,
        httponly=True,
        secure=settings.AUTH_COOKIE_SECURE,
        samesite=settings.AUTH_COOKIE_SAMESITE,
        path=settings.AUTH_COOKIE_PATH,
    )
    return AuthSessionResponse(
        user=UserResponse.model_validate(user),
        expires_in=expires_in,
    )


@router.post("/logout")
async def logout(response: Response) -> dict[str, str]:
    response.delete_cookie(
        key=settings.AUTH_COOKIE_NAME,
        path=settings.AUTH_COOKIE_PATH,
    )
    return {"status": "success"}


@router.get("/me", response_model=UserResponse)
async def me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserResponse:
    return UserResponse.model_validate(current_user)
