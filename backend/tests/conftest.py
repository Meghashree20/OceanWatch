import pytest

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
