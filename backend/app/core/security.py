from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import jwt
from pwdlib import PasswordHash

from app.core.config import settings


password_hash = PasswordHash.recommended()


class InvalidTokenError(ValueError):
    """Raised when an access token cannot be trusted."""


def hash_password(password: str) -> str:
    if not password:
        raise ValueError("Password must not be empty")
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    if not password or not hashed_password:
        return False
    return password_hash.verify(password, hashed_password)


def create_access_token(
    subject: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    if not subject:
        raise ValueError("Token subject must not be empty")

    secret = _get_jwt_secret()
    now = datetime.now(timezone.utc)
    expires_at = now + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=settings.AUTH_ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload = {
        "sub": subject,
        "type": "access",
        "iat": now,
        "exp": expires_at,
    }
    return jwt.encode(payload, secret, algorithm=settings.AUTH_JWT_ALGORITHM)


def decode_access_token(token: str) -> Dict[str, Any]:
    if not token:
        raise InvalidTokenError("Access token is required")

    try:
        payload = jwt.decode(
            token,
            _get_jwt_secret(),
            algorithms=[settings.AUTH_JWT_ALGORITHM],
            options={"require": ["sub", "type", "iat", "exp"]},
        )
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError) as exc:
        raise InvalidTokenError("Invalid or expired access token") from exc

    if payload.get("type") != "access" or not payload.get("sub"):
        raise InvalidTokenError("Invalid access token claims")
    return payload


def _get_jwt_secret() -> str:
    secret = settings.AUTH_JWT_SECRET
    if not secret or len(secret) < 32:
        raise RuntimeError(
            "AUTH_JWT_SECRET must be configured with at least 32 characters"
        )
    return secret
