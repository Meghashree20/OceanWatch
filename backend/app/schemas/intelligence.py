from typing import Any, Dict, List, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


AlertStatus = Literal["ACTIVE", "ACKNOWLEDGED", "UNDER_INVESTIGATION", "RESOLVED", "CLOSED"]


class AlertStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: AlertStatus


class OrganizationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=200)
    contact_email: EmailStr
    service_area: Dict[str, Any]
    areas_served: List[str] = Field(default_factory=list, max_length=100)
    email_notifications_enabled: bool = True
    acknowledgment_required: bool = False

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Organization name must not be blank.")
        return normalized

    @field_validator("service_area")
    @classmethod
    def validate_service_area(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        if value.get("type") != "Polygon":
            raise ValueError("service_area must be a GeoJSON Polygon.")
        coordinates = value.get("coordinates")
        if not isinstance(coordinates, list) or not coordinates:
            raise ValueError("service_area must include at least one polygon ring.")
        for ring in coordinates:
            if not isinstance(ring, list) or len(ring) < 4 or ring[0] != ring[-1]:
                raise ValueError("Each polygon ring must contain at least four points and be closed.")
            for point in ring:
                if (
                    not isinstance(point, list)
                    or len(point) != 2
                    or any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in point)
                    or not -180 <= point[0] <= 180
                    or not -90 <= point[1] <= 90
                ):
                    raise ValueError("GeoJSON coordinates must be finite longitude/latitude pairs in range.")
        return value

    @field_validator("areas_served")
    @classmethod
    def normalize_areas_served(cls, value: List[str]) -> List[str]:
        normalized = list(dict.fromkeys(" ".join(area.split()) for area in value if area.strip()))
        if any(len(area) > 200 for area in normalized):
            raise ValueError("Each served area must be at most 200 characters.")
        return normalized


class OrganizationVerificationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    verified: bool


class NotificationApproval(BaseModel):
    model_config = ConfigDict(extra="forbid")
    organization_id: str = Field(min_length=1, max_length=100)
    approved: Literal[True]


class NotificationAcknowledgment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    acknowledged: Literal[True]
