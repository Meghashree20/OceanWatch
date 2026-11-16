import os

import pytest

os.environ["OCEANWATCH_ENV"] = "test"
os.environ["MONGODB_URL"] = "mongodb://localhost:27017"
os.environ["MONGODB_DB_NAME"] = "oceanwatch_test"
os.environ["AUTH_JWT_SECRET"] = "test-only-secret-that-is-at-least-32-characters"
os.environ["SMTP_TEST_MODE"] = "true"
os.environ["SMTP_TEST_RECIPIENT"] = "oceanwatch-test@example.com"
os.environ["SMTP_HOST"] = "smtp.invalid"
os.environ["SMTP_USERNAME"] = ""
os.environ["SMTP_PASSWORD"] = ""
os.environ["SMTP_FROM_EMAIL"] = "oceanwatch-test@example.com"

from app.core.auth import require_active_user
from app.main import app
from app.models.user import User


@pytest.fixture(scope="module")
def authenticated_app():
    async def override_active_user():
        return User(
            user_id="test-user",
            full_name="Test User",
            email="test@example.com",
            password_hash="test-only",
        )

    app.dependency_overrides[require_active_user] = override_active_user
    yield app
    app.dependency_overrides.pop(require_active_user, None)
