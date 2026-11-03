from datetime import timedelta

import jwt
import pytest
from pydantic import ValidationError

from app.core import security
from app.core.config import settings
from app.models.user import User
from app.schemas.auth import LoginRequest, SignupRequest, UserResponse


@pytest.fixture(autouse=True)
def configured_jwt_secret(monkeypatch):
    monkeypatch.setattr(
        settings,
        "AUTH_JWT_SECRET",
        "test-only-secret-that-is-at-least-32-characters",
    )
    monkeypatch.setattr(settings, "AUTH_JWT_ALGORITHM", "HS256")


def test_password_hash_can_be_verified_without_exposing_plaintext():
    password = "correct horse battery staple"
    hashed = security.hash_password(password)

    assert hashed != password
    assert security.verify_password(password, hashed)


def test_incorrect_password_is_rejected():
    hashed = security.hash_password("correct-password")

    assert not security.verify_password("incorrect-password", hashed)


def test_access_token_contains_subject_and_decodes():
    token = security.create_access_token("user-123")

    payload = security.decode_access_token(token)

    assert payload["sub"] == "user-123"
    assert payload["type"] == "access"


def test_expired_access_token_is_rejected():
    token = security.create_access_token("user-123", timedelta(seconds=-1))

    with pytest.raises(security.InvalidTokenError):
        security.decode_access_token(token)


def test_invalid_access_token_is_rejected():
    with pytest.raises(security.InvalidTokenError):
        security.decode_access_token("not-a-jwt")


def test_missing_jwt_secret_fails_closed(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_JWT_SECRET", None)

    with pytest.raises(RuntimeError, match="AUTH_JWT_SECRET"):
        security.create_access_token("user-123")


def test_auth_schemas_validate_email_password_and_normalize_name():
    signup = SignupRequest(
        full_name="  Ocean   Researcher ",
        email="Researcher@example.com",
        password="secure-password",
        password_confirmation="secure-password",
    )
    login = LoginRequest(email="Researcher@example.com", password="secure-password")

    assert signup.full_name == "Ocean Researcher"
    assert str(signup.email) == "researcher@example.com"
    assert str(login.email) == "researcher@example.com"
    assert login.password == "secure-password"


def test_signup_schema_rejects_short_password():
    with pytest.raises(ValidationError):
        SignupRequest(
            full_name="Ocean Researcher",
            email="researcher@example.com",
            password="short",
            password_confirmation="short",
        )


def test_invalid_jwt_algorithm_cannot_be_used():
    token = jwt.encode(
        {"sub": "user-123", "type": "access"},
        "test-only-secret-that-is-at-least-32-characters",
        algorithm="HS384",
    )

    with pytest.raises(security.InvalidTokenError):
        security.decode_access_token(token)


def test_user_response_does_not_expose_password_hash():
    user = User(
        user_id="user-123",
        full_name="Ocean Researcher",
        email="Researcher@example.com",
        password_hash="argon2id$redacted",
    )

    response = UserResponse.model_validate(user)

    assert response.email == "researcher@example.com"
    assert "password_hash" not in response.model_dump()
