import pytest
from pydantic import ValidationError

from app.core.config import Settings


_TEST_SECRET = "unit-test-secret-that-is-long-enough-48-characters"


def _staging_settings(**overrides):
    values = {
        "OCEANWATCH_ENV": "staging",
        "MONGODB_URL": "mongodb+srv://user:password@cluster.example.invalid/",
        "MONGODB_DB_NAME": "oceanwatch_staging_acceptance",
        "AUTH_JWT_SECRET": _TEST_SECRET,
        "AUTH_COOKIE_SECURE": True,
        "BACKEND_CORS_ORIGINS": ["https://staging.example.invalid"],
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_staging_profile_accepts_isolated_tls_database_and_secure_cookie():
    settings = _staging_settings()

    assert settings.OCEANWATCH_ENV == "staging"
    assert settings.MONGODB_DB_NAME == "oceanwatch_staging_acceptance"
    assert settings.AUTH_COOKIE_SECURE is True
    assert settings.SMTP_TEST_MODE is True


@pytest.mark.parametrize(
    "overrides",
    [
        {"MONGODB_DB_NAME": "oceanwatch"},
        {"MONGODB_DB_NAME": "oceanwatch_test"},
        {"MONGODB_URL": "mongodb://localhost:27017"},
        {"MONGODB_URL": "mongodb://mongo.example.invalid:27017"},
        {"AUTH_COOKIE_SECURE": False},
        {"BACKEND_CORS_ORIGINS": ["http://staging.example.invalid"]},
    ],
)
def test_staging_profile_rejects_mixed_or_insecure_configuration(overrides):
    with pytest.raises(ValidationError):
        _staging_settings(**overrides)


def test_jwt_secret_must_meet_minimum_length():
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            OCEANWATCH_ENV="test",
            MONGODB_DB_NAME="oceanwatch_test",
            AUTH_JWT_SECRET="short",
        )


@pytest.mark.parametrize("environment", ["development", "test", "staging"])
def test_email_test_mode_cannot_be_disabled(environment):
    settings_values = {
        "OCEANWATCH_ENV": environment,
        "MONGODB_DB_NAME": f"oceanwatch_{environment}",
        "AUTH_JWT_SECRET": _TEST_SECRET,
        "SMTP_TEST_MODE": False,
    }
    if environment == "staging":
        settings_values.update({
            "MONGODB_URL": "mongodb+srv://user:password@cluster.example.invalid/",
            "MONGODB_DB_NAME": "oceanwatch_staging_acceptance",
            "AUTH_COOKIE_SECURE": True,
            "BACKEND_CORS_ORIGINS": ["https://staging.example.invalid"],
        })
    with pytest.raises(ValidationError, match="must remain enabled"):
        Settings(
            _env_file=None,
            **settings_values,
        )


def test_smtp_credentials_must_be_configured_as_a_pair():
    with pytest.raises(ValidationError, match="configured together"):
        Settings(
            _env_file=None,
            OCEANWATCH_ENV="test",
            MONGODB_DB_NAME="oceanwatch_test",
            AUTH_JWT_SECRET=_TEST_SECRET,
            SMTP_USERNAME="test-user",
        )
