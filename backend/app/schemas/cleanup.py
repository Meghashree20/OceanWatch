from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


OperationStatus = Literal[
    "PLANNED",
    "ASSIGNED",
    "INSPECTION_SCHEDULED",
    "CLEANUP_STARTED",
    "COMPLETED",
    "CANCELLED",
]
EvidenceType = Literal["BEFORE_PHOTO", "AFTER_PHOTO", "INSPECTION_NOTE", "SUPPORTING_EVIDENCE"]
WasteUnit = Literal["kg", "tonnes", "lb", "bags", "items", "other"]
QuantityClassification = Literal["ESTIMATED", "REPORTED", "INDEPENDENTLY_VERIFIED"]
CitizenReportCategory = Literal[
    "PLASTIC_DEBRIS",
    "FISHING_GEAR",
    "OIL_OR_CHEMICAL",
    "WILDLIFE_IMPACT",
    "OTHER",
]
CitizenReportStatus = Literal["PENDING", "UNDER_REVIEW", "VERIFIED", "REJECTED"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CleanupOperationCreate(StrictModel):
    recommendation_id: str = Field(min_length=64, max_length=64, pattern=r"^[a-f0-9]{64}$")
    scheduled_at: Optional[datetime] = None


class CleanupOperationAssignment(StrictModel):
    organization_id: str = Field(min_length=1, max_length=100)
    responsible_coordinator_user_id: Optional[str] = Field(None, min_length=1, max_length=100)
    scheduled_at: Optional[datetime] = None


class CleanupOperationStatusUpdate(StrictModel):
    status: OperationStatus
    reason: str = Field(min_length=3, max_length=500)


class EvidenceVerificationUpdate(StrictModel):
    status: Literal["VERIFIED", "REJECTED"]
    reason: str = Field(min_length=3, max_length=500)


class AssignmentNotificationApproval(StrictModel):
    approved: Literal[True]


class CleanupOperationCompletion(StrictModel):
    completed_at: datetime
    waste_quantity: Optional[float] = Field(None, ge=0, le=1_000_000_000)
    measurement_unit: Optional[WasteUnit] = None
    quantity_classification: Optional[QuantityClassification] = None
    verification_evidence_id: Optional[str] = Field(None, min_length=1, max_length=100)
    verifier_name: Optional[str] = Field(None, min_length=2, max_length=200)
    verifier_organization: Optional[str] = Field(None, min_length=2, max_length=200)

    @model_validator(mode="after")
    def validate_quantity_evidence(self):
        quantity_fields = (self.measurement_unit, self.quantity_classification)
        if self.waste_quantity is None and any(value is not None for value in quantity_fields):
            raise ValueError("A quantity, unit, and classification must be provided together.")
        if self.waste_quantity is not None and any(value is None for value in quantity_fields):
            raise ValueError("A quantity, unit, and classification must be provided together.")
        if self.quantity_classification == "INDEPENDENTLY_VERIFIED" and not all(
            (self.verification_evidence_id, self.verifier_name, self.verifier_organization)
        ):
            raise ValueError(
                "Independently verified quantities require evidence and verifier name and organization."
            )
        return self


class CitizenReportModeration(StrictModel):
    status: Literal["UNDER_REVIEW", "VERIFIED", "REJECTED"]
    reason: str = Field(min_length=3, max_length=500)
