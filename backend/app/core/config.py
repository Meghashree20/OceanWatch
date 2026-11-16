import os
import re
from pathlib import Path
from typing import List, Literal, Optional
from urllib.parse import parse_qs, urlsplit

from pydantic import EmailStr, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


_SUPPORTED_ENVIRONMENTS = {"development", "test", "staging"}
_ACTIVE_ENVIRONMENT = os.environ.get("OCEANWATCH_ENV", "development").strip().lower()
_BACKEND_DIR = Path(__file__).resolve().parents[2]

if _ACTIVE_ENVIRONMENT not in _SUPPORTED_ENVIRONMENTS:
    raise RuntimeError(
        "OCEANWATCH_ENV must be one of: development, test, staging."
    )


class Settings(BaseSettings):
    model_config = SettingsConfigDict(case_sensitive=True, env_file=None)

    OCEANWATCH_ENV: Literal["development", "test", "staging"] = _ACTIVE_ENVIRONMENT

    PROJECT_NAME: str = "OceanWatch API"
    API_V1_STR: str = "/api/v1"

    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = f"oceanwatch_{_ACTIVE_ENVIRONMENT}"
    MONGODB_SERVER_SELECTION_TIMEOUT_MS: int = 5000
    MONGODB_CONNECT_TIMEOUT_MS: int = 5000

    DBSCAN_EPS_KM: float = 150.0
    DBSCAN_MIN_SAMPLES: int = 10

    POLLUTION_RISK_MEDIUM_THRESHOLD: float = Field(default=1.0, ge=0.0)
    POLLUTION_RISK_HIGH_THRESHOLD: float = Field(default=10.0, ge=0.0)
    POLLUTION_RISK_CRITICAL_THRESHOLD: float = Field(default=100.0, ge=0.0)
    POLLUTION_TREND_WINDOW_DAYS: int = Field(default=90, ge=7, le=3650)
    POLLUTION_TREND_MIN_OBSERVATIONS: int = Field(default=3, ge=1, le=10000)
    POLLUTION_TREND_MIN_RELATIVE_CHANGE: float = Field(default=0.25, ge=0.0, le=10.0)
    POLLUTION_TREND_CELL_SIZE_DEGREES: float = Field(default=1.0, gt=0.0, le=10.0)
    POLLUTION_DATA_FRESHNESS_MAX_DAYS: int = Field(default=90, ge=1, le=3650)

    AUTH_JWT_SECRET: str = Field(min_length=32, repr=False)
    AUTH_JWT_ALGORITHM: str = "HS256"
    AUTH_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, ge=1, le=1440)
    AUTH_COOKIE_NAME: str = "oceanwatch_access_token"
    AUTH_COOKIE_SECURE: bool = False
    AUTH_COOKIE_SAMESITE: Literal["lax", "strict", "none"] = "lax"
    AUTH_COOKIE_PATH: str = "/"

    SATELLITE_MODEL_PATH: str = "models/model.pth"
    SATELLITE_SAMPLES_DIR: str = "samples"
    SATELLITE_DEVICE: str = "cpu"
    SATELLITE_CONFIDENCE_THRESHOLD: float = Field(default=0.5, ge=0.0, le=1.0)
    SATELLITE_PROVENANCE_PUBLIC_KEY: Optional[str] = None

    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = Field(default=587, ge=1, le=65535)
    SMTP_USERNAME: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = Field(default=None, repr=False)
    SMTP_FROM_EMAIL: Optional[EmailStr] = None
    SMTP_SECURITY: Literal["starttls", "ssl"] = "starttls"
    SMTP_TIMEOUT_SECONDS: int = Field(default=15, ge=1, le=120)
    SMTP_TEST_MODE: bool = True
    SMTP_TEST_RECIPIENT: Optional[EmailStr] = None

    PRIVATE_MEDIA_DIR: str = "private_media"
    PRIVATE_MEDIA_MAX_BYTES: int = Field(default=5 * 1024 * 1024, ge=1024, le=25 * 1024 * 1024)
    PRIVATE_MEDIA_MAX_PIXELS: int = Field(default=20_000_000, ge=1024, le=50_000_000)

    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
    ]

    @field_validator("AUTH_JWT_SECRET")
    @classmethod
    def validate_jwt_secret(cls, value: str) -> str:
        if value != value.strip():
            raise ValueError("AUTH_JWT_SECRET must not have leading or trailing whitespace.")
        return value

    @model_validator(mode="after")
    def validate_environment_safety(self) -> "Settings":
        expected_db_prefix = f"oceanwatch_{self.OCEANWATCH_ENV}"
        if not re.fullmatch(
            rf"{re.escape(expected_db_prefix)}(?:_[a-z0-9][a-z0-9_-]*)?",
            self.MONGODB_DB_NAME,
            flags=re.IGNORECASE,
        ):
            raise ValueError(
                f"MONGODB_DB_NAME must be isolated under the {self.OCEANWATCH_ENV} profile."
            )

        if bool(self.SMTP_USERNAME) != bool(self.SMTP_PASSWORD):
            raise ValueError("SMTP_USERNAME and SMTP_PASSWORD must be configured together.")
        if self.SMTP_HOST and not self.SMTP_FROM_EMAIL:
            raise ValueError("SMTP_FROM_EMAIL is required when SMTP_HOST is configured.")
        if self.SMTP_FROM_EMAIL and not self.SMTP_HOST:
            raise ValueError("SMTP_HOST is required when SMTP_FROM_EMAIL is configured.")

        if not self.SMTP_TEST_MODE:
            raise ValueError(
                "SMTP_TEST_MODE must remain enabled; external organization delivery is disabled."
            )

        if self.OCEANWATCH_ENV == "staging":
            if self.AUTH_JWT_SECRET.lower().startswith(
                ("test", "example", "replace", "change-me")
            ):
                raise ValueError("Staging requires a generated, non-placeholder AUTH_JWT_SECRET.")
            if not self.AUTH_COOKIE_SECURE:
                raise ValueError("AUTH_COOKIE_SECURE must be true in staging.")
            if not self.BACKEND_CORS_ORIGINS or any(
                urlsplit(origin).scheme != "https"
                or urlsplit(origin).hostname in {"localhost", "127.0.0.1", "::1"}
                for origin in self.BACKEND_CORS_ORIGINS
            ):
                raise ValueError("Staging BACKEND_CORS_ORIGINS must contain only HTTPS origins.")
            if not self.MONGODB_DB_NAME.startswith("oceanwatch_staging_"):
                raise ValueError("Staging MONGODB_DB_NAME must include a unique staging suffix.")

            parsed_uri = urlsplit(self.MONGODB_URL)
            host = (parsed_uri.hostname or "").lower()
            if parsed_uri.scheme not in {"mongodb", "mongodb+srv"} or not host:
                raise ValueError("Staging requires a valid remote MongoDB connection URI.")
            if host in {"localhost", "127.0.0.1", "::1"}:
                raise ValueError("Staging must not connect to a local MongoDB instance.")
            if parsed_uri.scheme == "mongodb":
                query = parse_qs(parsed_uri.query)
                tls_enabled = (query.get("tls") or query.get("ssl") or ["false"])[-1].lower()
                if tls_enabled not in {"true", "1"}:
                    raise ValueError("Staging MongoDB connections must enable TLS.")

        return self


_PROFILE_ENV_FILE = _BACKEND_DIR / f".env.{_ACTIVE_ENVIRONMENT}"
settings = Settings(_env_file=_PROFILE_ENV_FILE)
if settings.OCEANWATCH_ENV != _ACTIVE_ENVIRONMENT:
    raise RuntimeError(
        "OCEANWATCH_ENV in the selected profile file must match the process environment."
    )
