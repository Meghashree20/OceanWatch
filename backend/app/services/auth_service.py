from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pymongo.errors import DuplicateKeyError

from app.core import security
from app.db.mongodb import db_client
from app.models.user import User


class AuthServiceError(Exception):
    """Base class for expected authentication service errors."""


class DuplicateEmailError(AuthServiceError):
    """Raised when an email is already registered."""


class InvalidCredentialsError(AuthServiceError):
    """Raised when login credentials are not valid."""


class UserNotFoundError(AuthServiceError):
    """Raised when a referenced user does not exist."""


class InactiveUserError(AuthServiceError):
    """Raised when a user account is inactive."""


class AuthService:
    def __init__(self, database: Any = None):
        self.database = database

    @property
    def users(self) -> Any:
        database = self.database if self.database is not None else db_client.db
        if database is None:
            raise RuntimeError("MongoDB is not connected")
        return database["users"]

    async def register_user(
        self,
        *,
        full_name: str,
        email: str,
        password: str,
    ) -> User:
        normalized_email = _normalize_email(email)
        if await self.users.find_one({"email": normalized_email}, {"_id": 0}):
            raise DuplicateEmailError("An account with this email already exists")

        now = datetime.now(timezone.utc)
        user = User(
            user_id=str(uuid4()),
            full_name=full_name,
            email=normalized_email,
            password_hash=security.hash_password(password),
            created_at=now,
            updated_at=now,
        )
        try:
            await self.users.insert_one(user.model_dump())
        except DuplicateKeyError as exc:
            raise DuplicateEmailError("An account with this email already exists") from exc
        return user

    async def authenticate_user(self, *, email: str, password: str) -> User:
        user = await self.users.find_one({"email": _normalize_email(email)}, {"_id": 0})
        if not user:
            raise InvalidCredentialsError("Invalid email or password")

        stored_user = User.from_mongo(user)
        if not security.verify_password(password, stored_user.password_hash):
            raise InvalidCredentialsError("Invalid email or password")
        if not stored_user.is_active:
            raise InactiveUserError("User account is inactive")
        return stored_user

    async def get_user(self, user_id: str, *, require_active: bool = True) -> User:
        user = await self.users.find_one({"user_id": user_id}, {"_id": 0})
        if not user:
            raise UserNotFoundError("User not found")
        stored_user = User.from_mongo(user)
        if require_active and not stored_user.is_active:
            raise InactiveUserError("User account is inactive")
        return stored_user


def _normalize_email(email: str) -> str:
    return email.strip().lower()
