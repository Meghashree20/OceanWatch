from datetime import datetime, timezone
from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator


class User(BaseModel):
    """MongoDB representation of an OceanWatch user."""

    model_config = ConfigDict(extra="forbid")

    user_id: str = Field(min_length=1)
    full_name: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=320)
    password_hash: str = Field(min_length=1)
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return str(value).strip().lower()

    @classmethod
    def from_mongo(cls, document: Mapping[str, Any]) -> "User":
        """Create a user model from a MongoDB document."""
        return cls.model_validate({key: value for key, value in document.items() if key != "_id"})
