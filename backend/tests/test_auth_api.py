from datetime import timedelta
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from pymongo.errors import DuplicateKeyError

from app.core import security
from app.core.config import settings
from app.db.mongodb import db_client
from app.main import app
from app.models.user import User


class FakeUsersCollection:
    def __init__(self):
        self.documents: dict[str, dict[str, Any]] = {}

    async def find_one(self, query: dict[str, Any], projection: dict[str, int] | None = None):
        for document in self.documents.values():
            if all(document.get(key) == value for key, value in query.items()):
                return {key: value for key, value in document.items() if key != "_id"}
        return None

    async def insert_one(self, document: dict[str, Any]):
        if document["email"] in self.documents:
            raise DuplicateKeyError("duplicate email")
        self.documents[document["email"]] = document


class FakeDatabase:
    def __init__(self):
        self.users = FakeUsersCollection()

    def __getitem__(self, collection_name: str):
        assert collection_name == "users"
        return self.users


@pytest_asyncio.fixture
async def auth_client(monkeypatch):
    database = FakeDatabase()
    monkeypatch.setattr(db_client, "db", database)
    monkeypatch.setattr(
        settings,
        "AUTH_JWT_SECRET",
        "test-only-secret-that-is-at-least-32-characters",
    )
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client, database


@pytest.mark.asyncio
async def test_successful_signup_and_email_normalization(auth_client):
    client, database = auth_client

    response = await client.post(
        "/api/auth/signup",
        json={
            "full_name": "Ocean Researcher",
            "email": "Researcher@Example.COM",
            "password": "secure-password",
            "password_confirmation": "secure-password",
        },
    )

    assert response.status_code == 201
    assert response.json()["email"] == "researcher@example.com"
    assert "password_hash" not in response.json()
    assert database.users.documents["researcher@example.com"]["password_hash"]


@pytest.mark.asyncio
async def test_duplicate_email_signup_returns_conflict(auth_client):
    client, _ = auth_client
    payload = {
        "full_name": "Ocean Researcher",
        "email": "researcher@example.com",
        "password": "secure-password",
        "password_confirmation": "secure-password",
    }

    assert (await client.post("/api/auth/signup", json=payload)).status_code == 201
    duplicate = await client.post("/api/auth/signup", json=payload)

    assert duplicate.status_code == 409


@pytest.mark.asyncio
async def test_successful_login_sets_httponly_cookie(auth_client):
    client, _ = auth_client
    await client.post(
        "/api/auth/signup",
        json={
            "full_name": "Ocean Researcher",
            "email": "researcher@example.com",
            "password": "secure-password",
            "password_confirmation": "secure-password",
        },
    )

    response = await client.post(
        "/api/auth/login",
        json={"email": "RESEARCHER@example.com", "password": "secure-password"},
    )

    assert response.status_code == 200
    assert response.json()["user"]["email"] == "researcher@example.com"
    assert "oceanwatch_access_token=" in response.headers["set-cookie"]
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "access_token" not in response.json()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "email,password",
    [
        ("researcher@example.com", "wrong-password"),
        ("unknown@example.com", "secure-password"),
    ],
)
async def test_invalid_login_credentials_are_generic(auth_client, email, password):
    client, _ = auth_client
    await client.post(
        "/api/auth/signup",
        json={
            "full_name": "Ocean Researcher",
            "email": "researcher@example.com",
            "password": "secure-password",
            "password_confirmation": "secure-password",
        },
    )

    response = await client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )

    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Invalid email or password"


@pytest.mark.asyncio
async def test_me_requires_valid_token_and_returns_current_user(auth_client):
    client, database = auth_client
    user = User(
        user_id="user-123",
        full_name="Ocean Researcher",
        email="researcher@example.com",
        password_hash=security.hash_password("secure-password"),
    )
    database.users.documents[user.email] = user.model_dump()

    no_token = await client.get("/api/auth/me")
    assert no_token.status_code == 401

    token = security.create_access_token(user.user_id)
    client.cookies.set(settings.AUTH_COOKIE_NAME, token)
    authenticated = await client.get("/api/auth/me")

    assert authenticated.status_code == 200
    assert authenticated.json()["user_id"] == "user-123"
    assert "password_hash" not in authenticated.json()


@pytest.mark.asyncio
async def test_expired_and_invalid_tokens_are_rejected(auth_client):
    client, _ = auth_client
    for token in (
        security.create_access_token("user-123", expires_delta=timedelta(seconds=-1)),
        "not-a-valid-token",
    ):
        client.cookies.set(settings.AUTH_COOKIE_NAME, token)
        response = await client.get("/api/auth/me")
        assert response.status_code == 401


@pytest.mark.asyncio
async def test_inactive_user_is_rejected(auth_client):
    client, database = auth_client
    user = User(
        user_id="inactive-123",
        full_name="Inactive User",
        email="inactive@example.com",
        password_hash=security.hash_password("secure-password"),
        is_active=False,
    )
    database.users.documents[user.email] = user.model_dump()
    client.cookies.set(settings.AUTH_COOKIE_NAME, security.create_access_token(user.user_id))

    response = await client.get("/api/auth/me")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_logout_clears_authentication_cookie(auth_client):
    client, _ = auth_client
    client.cookies.set(settings.AUTH_COOKIE_NAME, "token")

    response = await client.post("/api/auth/logout")

    assert response.status_code == 200
    assert "Max-Age=0" in response.headers["set-cookie"]
    assert "oceanwatch_access_token=" in response.headers["set-cookie"]
