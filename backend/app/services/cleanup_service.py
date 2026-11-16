"""Cleanup recommendations, operation workflow, evidence, and response analytics."""

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.core.config import settings
from app.db.mongodb import db_client
from app.schemas.cleanup import CleanupOperationCompletion
from app.services.intelligence_service import IntelligenceService
from app.services.private_media import PrivateMediaStore
from pymongo.errors import DuplicateKeyError


OPERATION_COLLECTION = "cleanup_operations"
EVIDENCE_COLLECTION = "cleanup_operation_evidence"
MEDIA_COLLECTION = "private_media"
NOTIFICATION_COLLECTION = "cleanup_operation_notifications"
ACTIVE_OPERATION_STATUSES = {
    "PLANNED", "ASSIGNED", "INSPECTION_SCHEDULED", "CLEANUP_STARTED"
}
STATUS_TRANSITIONS = {
    "PLANNED": {"ASSIGNED", "INSPECTION_SCHEDULED", "CANCELLED"},
    "ASSIGNED": {"PLANNED", "INSPECTION_SCHEDULED", "CLEANUP_STARTED", "CANCELLED"},
    "INSPECTION_SCHEDULED": {"ASSIGNED", "CLEANUP_STARTED", "CANCELLED"},
    "CLEANUP_STARTED": {"COMPLETED", "CANCELLED"},
    "COMPLETED": set(),
    "CANCELLED": set(),
}


def _utc_datetime(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class CleanupService:
    @staticmethod
    async def get_operation(operation_id: str) -> Optional[Dict[str, Any]]:
        return await db_client.db[OPERATION_COLLECTION].find_one(
            {"operation_id": operation_id}, {"_id": 0, "active_recommendation_key": 0}
        )

    @staticmethod
    async def list_operations(
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Dict[str, Any]:
        collection = db_client.db[OPERATION_COLLECTION]
        query = {"status": status} if status else {}
        cursor = collection.find(
            query, {"_id": 0, "active_recommendation_key": 0}
        ).sort("updated_at", -1).skip(skip).limit(limit)
        return {
            "data": await cursor.to_list(length=limit),
            "total": await collection.count_documents(query),
            "skip": skip,
            "limit": limit,
        }

    @staticmethod
    async def create_operation(
        recommendation_id: str,
        scheduled_at: Optional[datetime],
        actor_id: str,
    ) -> Dict[str, Any]:
        from app.services.recommendation_service import RecommendationService

        recommendation_result = await RecommendationService.get_cleanup_recommendations(limit=500)
        recommendation = next(
            (
                item for item in recommendation_result["data"]
                if item["recommendation_id"] == recommendation_id
            ),
            None,
        )
        if recommendation is None:
            raise KeyError("Current cleanup recommendation not found.")
        collection = db_client.db[OPERATION_COLLECTION]
        existing = await collection.find_one(
            {
                "recommendation_id": recommendation_id,
                "status": {"$in": list(ACTIVE_OPERATION_STATUSES)},
            },
            {"_id": 0, "active_recommendation_key": 0},
        )
        if existing is not None:
            return existing
        now = datetime.now(timezone.utc)
        if scheduled_at is not None and _utc_datetime(scheduled_at) <= now:
            raise ValueError("Scheduled date must be in the future.")
        document = {
            "operation_id": uuid4().hex,
            "recommendation_id": recommendation_id,
            "active_recommendation_key": recommendation_id,
            "recommendation_snapshot": recommendation,
            "location": recommendation["location"],
            "alert_id": (recommendation.get("evidence", {}).get("active_alert") or {}).get("alert_id"),
            "assigned_organization_id": None,
            "responsible_coordinator_user_id": actor_id,
            "scheduled_at": _utc_datetime(scheduled_at) if scheduled_at else None,
            "status": "PLANNED",
            "completion": None,
            "created_by": actor_id,
            "created_at": now,
            "updated_at": now,
            "status_history": [{
                "status": "PLANNED",
                "changed_at": now,
                "changed_by": actor_id,
                "reason": "Operation created from a current cleanup recommendation.",
            }],
            "audit_history": [{
                "event": "CREATED",
                "at": now,
                "actor_id": actor_id,
                "reason": "Operation created from a current cleanup recommendation.",
            }],
        }
        try:
            await collection.insert_one(document)
        except DuplicateKeyError:
            existing = await collection.find_one(
                {"active_recommendation_key": recommendation_id},
                {"_id": 0, "active_recommendation_key": 0},
            )
            if existing is None:
                raise
            return existing
        return {
            key: value
            for key, value in document.items()
            if key not in {"_id", "active_recommendation_key"}
        }

    @staticmethod
    async def _verified_organization(
        organization_id: str,
        location: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        query: Dict[str, Any] = {"organization_id": organization_id, "verified": True}
        if location:
            query["service_area"] = {
                "$geoIntersects": {
                    "$geometry": {
                        "type": "Point",
                        "coordinates": [location["longitude"], location["latitude"]],
                    }
                }
            }
        organization = await db_client.db["environmental_organizations"].find_one(
            query,
            {"_id": 0},
        )
        if organization is None:
            raise ValueError("Assigned organization must be verified and serve the operation location.")
        return organization

    @staticmethod
    async def _active_coordinator(user_id: str) -> Dict[str, Any]:
        user = await db_client.db["users"].find_one(
            {"user_id": user_id, "is_active": True},
            {"_id": 0, "user_id": 1, "full_name": 1},
        )
        if user is None:
            raise ValueError("Responsible coordinator must be an active OceanWatch user.")
        return user

    @staticmethod
    async def assign_operation(
        operation_id: str,
        organization_id: str,
        coordinator_user_id: Optional[str],
        scheduled_at: Optional[datetime],
        actor_id: str,
    ) -> Dict[str, Any]:
        collection = db_client.db[OPERATION_COLLECTION]
        operation = await CleanupService.get_operation(operation_id)
        if operation is None:
            raise KeyError("Cleanup operation not found.")
        if operation["status"] not in {"PLANNED", "ASSIGNED", "INSPECTION_SCHEDULED"}:
            raise ValueError("Organization assignment is not allowed in the current operation status.")
        organization = await CleanupService._verified_organization(organization_id, operation["location"])
        coordinator_id = coordinator_user_id or actor_id
        coordinator = await CleanupService._active_coordinator(coordinator_id)
        now = datetime.now(timezone.utc)
        if scheduled_at is not None and _utc_datetime(scheduled_at) <= now:
            raise ValueError("Scheduled date must be in the future.")
        assignments = {
            "assigned_organization_id": organization_id,
            "assigned_organization_name": organization["name"],
            "responsible_coordinator_user_id": coordinator_id,
            "responsible_coordinator_name": coordinator["full_name"],
            "updated_at": now,
        }
        if scheduled_at is not None:
            assignments["scheduled_at"] = _utc_datetime(scheduled_at)
        status = operation["status"]
        update: Dict[str, Any] = {"$set": assignments}
        audit_event = {
            "event": "ASSIGNED",
            "at": now,
            "actor_id": actor_id,
            "organization_id": organization_id,
            "coordinator_user_id": coordinator_id,
        }
        if status == "PLANNED":
            assignments["status"] = "ASSIGNED"
            update["$push"] = {
                "status_history": {
                    "status": "ASSIGNED",
                    "changed_at": now,
                    "changed_by": actor_id,
                    "reason": "Verified organization and active coordinator assigned.",
                },
                "audit_history": audit_event,
            }
        else:
            update["$push"] = {"audit_history": audit_event}
        result = await collection.update_one(
            {"operation_id": operation_id, "status": status},
            update,
        )
        if not result.matched_count:
            raise ValueError("Operation changed during assignment; reload and retry.")
        return await CleanupService.get_operation(operation_id)

    @staticmethod
    async def update_status(
        operation_id: str,
        new_status: str,
        reason: str,
        actor_id: str,
    ) -> Dict[str, Any]:
        operation = await CleanupService.get_operation(operation_id)
        if operation is None:
            raise KeyError("Cleanup operation not found.")
        old_status = operation["status"]
        if new_status == "COMPLETED":
            raise ValueError("Use the completion endpoint to record completion evidence.")
        if new_status not in STATUS_TRANSITIONS[old_status]:
            raise ValueError(f"Operation cannot transition from {old_status} to {new_status}.")
        if new_status == "ASSIGNED" and not operation.get("assigned_organization_id"):
            raise ValueError("Assign a verified organization before moving to Assigned.")
        if new_status == "INSPECTION_SCHEDULED" and not operation.get("scheduled_at"):
            raise ValueError("Set a scheduled date before scheduling an inspection.")
        if new_status == "CLEANUP_STARTED" and not operation.get("assigned_organization_id"):
            raise ValueError("Assign an organization before starting cleanup.")
        now = datetime.now(timezone.utc)
        update: Dict[str, Any] = {
            "$set": {"status": new_status, "updated_at": now},
            "$push": {
                "status_history": {
                    "status": new_status,
                    "changed_at": now,
                    "changed_by": actor_id,
                    "reason": reason,
                },
                "audit_history": {
                    "event": "STATUS_CHANGED",
                    "at": now,
                    "actor_id": actor_id,
                    "from_status": old_status,
                    "to_status": new_status,
                    "reason": reason,
                },
            },
        }
        if new_status == "CANCELLED":
            update["$unset"] = {"active_recommendation_key": ""}
        result = await db_client.db[OPERATION_COLLECTION].update_one(
            {"operation_id": operation_id, "status": old_status},
            update,
        )
        if not result.matched_count:
            raise ValueError("Operation changed during status update; reload and retry.")
        return await CleanupService.get_operation(operation_id)

    @staticmethod
    async def list_evidence(operation_id: str) -> List[Dict[str, Any]]:
        cursor = db_client.db[EVIDENCE_COLLECTION].find(
            {"operation_id": operation_id}, {"_id": 0}
        ).sort("created_at", 1)
        return await cursor.to_list(length=1000)

    @staticmethod
    async def get_evidence_media(evidence_id: str) -> Optional[Dict[str, Any]]:
        evidence = await db_client.db[EVIDENCE_COLLECTION].find_one(
            {"evidence_id": evidence_id}, {"_id": 0}
        )
        if evidence is None or not evidence.get("media_id"):
            return None
        media = await CleanupService.get_media(
            evidence["media_id"], "cleanup_operation", evidence["operation_id"]
        )
        if media is None or not media["path"].is_file():
            return None
        return {**evidence, "media": media}

    @staticmethod
    async def add_evidence(
        operation_id: str,
        evidence_type: str,
        notes: Optional[str],
        upload: Any,
        actor_id: str,
    ) -> Dict[str, Any]:
        operation = await CleanupService.get_operation(operation_id)
        if operation is None:
            raise KeyError("Cleanup operation not found.")
        if operation["status"] in {"COMPLETED", "CANCELLED"}:
            raise ValueError("Evidence cannot be added to a completed or cancelled operation.")
        if evidence_type in {"BEFORE_PHOTO", "AFTER_PHOTO", "SUPPORTING_EVIDENCE"} and upload is None:
            raise ValueError("A photo or supporting image file is required for this evidence type.")
        if evidence_type == "INSPECTION_NOTE" and not (notes and notes.strip()):
            raise ValueError("Inspection notes must not be blank.")
        media = None
        if upload is not None:
            media = await PrivateMediaStore.store_image(upload)
        now = datetime.now(timezone.utc)
        evidence_id = uuid4().hex
        media_id = uuid4().hex if media else None
        try:
            if media:
                await db_client.db[MEDIA_COLLECTION].insert_one({
                    "media_id": media_id,
                    "storage_key": media["storage_key"],
                    "content_type": media["content_type"],
                    "extension": media["extension"],
                    "size_bytes": media["size_bytes"],
                    "sha256": media["sha256"],
                    "width": media["width"],
                    "height": media["height"],
                    "parent_type": "cleanup_operation",
                    "parent_id": operation_id,
                    "uploaded_by": actor_id,
                    "created_at": now,
                })
            evidence = {
                "evidence_id": evidence_id,
                "operation_id": operation_id,
                "evidence_type": evidence_type,
                "notes": notes.strip() if notes else None,
                "media_id": media_id,
                "submitted_by": actor_id,
                "created_at": now,
                "verification_status": "PENDING",
                "verification_history": [{
                    "status": "PENDING",
                    "changed_at": now,
                    "changed_by": actor_id,
                    "reason": "Evidence awaits review.",
                }],
            }
            await db_client.db[EVIDENCE_COLLECTION].insert_one(evidence)
            await db_client.db[OPERATION_COLLECTION].update_one(
                {"operation_id": operation_id},
                {
                    "$set": {"updated_at": now},
                    "$push": {
                        "audit_history": {
                            "event": "EVIDENCE_SUBMITTED",
                            "at": now,
                            "actor_id": actor_id,
                            "evidence_id": evidence_id,
                            "evidence_type": evidence_type,
                        }
                    },
                },
            )
        except Exception:
            if media:
                PrivateMediaStore.delete(media)
                await db_client.db[MEDIA_COLLECTION].delete_one({"media_id": media_id})
            raise
        return {key: value for key, value in evidence.items() if key != "_id"}

    @staticmethod
    async def verify_evidence(
        operation_id: str,
        evidence_id: str,
        status: str,
        reason: str,
        actor_id: str,
    ) -> Optional[Dict[str, Any]]:
        operation = await CleanupService.get_operation(operation_id)
        if operation is None:
            return None
        collection = db_client.db[EVIDENCE_COLLECTION]
        evidence = await collection.find_one(
            {"operation_id": operation_id, "evidence_id": evidence_id}, {"_id": 0}
        )
        if evidence is None:
            return None
        if evidence["verification_status"] != "PENDING":
            raise ValueError("Only pending evidence can be verified or rejected.")
        now = datetime.now(timezone.utc)
        result = await collection.update_one(
            {
                "operation_id": operation_id,
                "evidence_id": evidence_id,
                "verification_status": "PENDING",
            },
            {
                "$set": {
                    "verification_status": status,
                    "verified_at": now,
                    "verified_by": actor_id,
                },
                "$push": {
                    "verification_history": {
                        "status": status,
                        "changed_at": now,
                        "changed_by": actor_id,
                        "reason": reason,
                    }
                },
            },
        )
        if not result.matched_count:
            raise ValueError("Evidence status changed during review; reload and retry.")
        await db_client.db[OPERATION_COLLECTION].update_one(
            {"operation_id": operation_id},
            {
                "$set": {"updated_at": now},
                "$push": {
                    "audit_history": {
                        "event": "EVIDENCE_REVIEWED",
                        "at": now,
                        "actor_id": actor_id,
                        "evidence_id": evidence_id,
                        "verification_status": status,
                        "reason": reason,
                    }
                },
            },
        )
        return await collection.find_one(
            {"operation_id": operation_id, "evidence_id": evidence_id}, {"_id": 0}
        )

    @staticmethod
    async def get_media(media_id: str, parent_type: str, parent_id: str) -> Optional[Dict[str, Any]]:
        media = await db_client.db[MEDIA_COLLECTION].find_one(
            {
                "media_id": media_id,
                "parent_type": parent_type,
                "parent_id": parent_id,
            },
            {"_id": 0},
        )
        if media is not None:
            media["path"] = PrivateMediaStore.path_for(media)
        return media

    @staticmethod
    async def _operation_notification_body(operation: Dict[str, Any]) -> tuple[str, str, str]:
        organization_id = operation.get("assigned_organization_id")
        if not organization_id:
            raise ValueError("Assign an organization before sending an operation notification.")
        organization = await CleanupService._verified_organization(
            organization_id, operation.get("location")
        )
        if not organization.get("email_notifications_enabled", False):
            raise ValueError("Organization has not enabled email notifications.")
        subject = f"OceanWatch cleanup operation assignment {operation['operation_id'][:8]}"
        body = (
            f"Hello {organization['name']},\n\n"
            "You have been assigned an OceanWatch cleanup response operation.\n"
            f"Operation: {operation['operation_id']}\n"
            f"Status: {operation['status']}\n"
            f"Location: {operation['location']['latitude']}, {operation['location']['longitude']}\n"
            f"Scheduled date: {operation.get('scheduled_at') or 'Not scheduled'}\n\n"
            "Review the operation and submit inspection or completion updates through the authorized OceanWatch workflow. "
            "This assignment is not evidence that pollution has decreased."
        )
        return organization["contact_email"], subject, body

    @staticmethod
    async def send_assignment_notification(
        operation_id: str,
        approved: bool,
        actor_id: str,
    ) -> Dict[str, Any]:
        if not approved:
            raise ValueError("Administrator approval is required before notification delivery.")
        operation = await CleanupService.get_operation(operation_id)
        if operation is None:
            raise KeyError("Cleanup operation not found.")
        if operation["status"] not in ACTIVE_OPERATION_STATUSES:
            raise ValueError("Only active cleanup operations can be notified.")
        intended_recipient, subject, body = await CleanupService._operation_notification_body(operation)
        recipient, subject, body = IntelligenceService._notification_delivery(
            intended_recipient, subject, body
        )
        collection = db_client.db[NOTIFICATION_COLLECTION]
        existing = await collection.find_one(
            {"operation_id": operation_id, "organization_id": operation["assigned_organization_id"]},
            {"_id": 0},
        )
        if existing and existing["delivery_status"] in {"PENDING", "SENT", "ACKNOWLEDGED"}:
            raise ValueError(f"Assignment notification already has status {existing['delivery_status']}.")
        now = datetime.now(timezone.utc)
        notification_id = existing["notification_id"] if existing else uuid4().hex
        if existing:
            claimed = await collection.update_one(
                {"notification_id": notification_id, "delivery_status": "FAILED"},
                {"$set": {
                    "delivery_status": "PENDING",
                    "recipient_email": recipient,
                    "intended_recipient_email": intended_recipient,
                    "test_mode": settings.SMTP_TEST_MODE,
                    "subject": subject,
                    "approved_by": actor_id,
                    "updated_at": now,
                }},
            )
            if claimed.matched_count != 1:
                raise ValueError("Assignment notification is already being processed.")
        else:
            try:
                await collection.insert_one({
                    "notification_id": notification_id,
                    "operation_id": operation_id,
                    "organization_id": operation["assigned_organization_id"],
                    "recipient_email": recipient,
                    "intended_recipient_email": intended_recipient,
                    "test_mode": settings.SMTP_TEST_MODE,
                    "subject": subject,
                    "delivery_status": "PENDING",
                    "approved_by": actor_id,
                    "approved_at": now,
                    "created_at": now,
                    "updated_at": now,
                    "acknowledged_at": None,
                })
            except DuplicateKeyError as exc:
                raise ValueError("An assignment notification is already being processed or recorded.") from exc
        try:
            await asyncio.to_thread(
                IntelligenceService._send_email, recipient, subject, body
            )
        except Exception as exc:
            await collection.update_one(
                {"notification_id": notification_id},
                {"$set": {
                    "delivery_status": "FAILED",
                    "delivery_error": type(exc).__name__,
                    "updated_at": datetime.now(timezone.utc),
                }},
            )
            raise RuntimeError("Email provider failed to send the approved assignment notification.") from exc
        await collection.update_one(
            {"notification_id": notification_id},
            {"$set": {
                "delivery_status": "SENT",
                "sent_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }},
        )
        await db_client.db[OPERATION_COLLECTION].update_one(
            {"operation_id": operation_id},
            {
                "$set": {"updated_at": datetime.now(timezone.utc)},
                "$push": {
                    "audit_history": {
                        "event": "ASSIGNMENT_NOTIFICATION_SENT",
                        "at": datetime.now(timezone.utc),
                        "actor_id": actor_id,
                        "notification_id": notification_id,
                    }
                },
            },
        )
        return await collection.find_one({"notification_id": notification_id}, {"_id": 0})

    @staticmethod
    async def list_notifications(operation_id: str) -> Dict[str, Any]:
        cursor = db_client.db[NOTIFICATION_COLLECTION].find(
            {"operation_id": operation_id}, {"_id": 0}
        ).sort("created_at", -1)
        data = await cursor.to_list(length=500)
        return {
            "data": data,
            "total": len(data),
            "test_mode": settings.SMTP_TEST_MODE,
            "delivery_recipient_email": (
                str(settings.SMTP_TEST_RECIPIENT)
                if settings.SMTP_TEST_MODE and settings.SMTP_TEST_RECIPIENT
                else None
            ),
        }

    @staticmethod
    async def acknowledge_assignment(notification_id: str, actor_id: str) -> Optional[Dict[str, Any]]:
        collection = db_client.db[NOTIFICATION_COLLECTION]
        result = await collection.update_one(
            {"notification_id": notification_id, "delivery_status": "SENT"},
            {"$set": {
                "delivery_status": "ACKNOWLEDGED",
                "acknowledged_at": datetime.now(timezone.utc),
                "acknowledged_by": actor_id,
                "updated_at": datetime.now(timezone.utc),
            }},
        )
        if not result.matched_count:
            return None
        notification = await collection.find_one({"notification_id": notification_id}, {"_id": 0})
        await db_client.db[OPERATION_COLLECTION].update_one(
            {"operation_id": notification["operation_id"]},
            {
                "$set": {"updated_at": datetime.now(timezone.utc)},
                "$push": {
                    "audit_history": {
                        "event": "ASSIGNMENT_ACKNOWLEDGED",
                        "at": datetime.now(timezone.utc),
                        "actor_id": actor_id,
                        "notification_id": notification_id,
                    }
                },
            },
        )
        return notification

    @staticmethod
    async def complete_operation(
        operation_id: str,
        completion: CleanupOperationCompletion,
        actor_id: str,
    ) -> Dict[str, Any]:
        operation = await CleanupService.get_operation(operation_id)
        if operation is None:
            raise KeyError("Cleanup operation not found.")
        if operation["status"] != "CLEANUP_STARTED":
            raise ValueError("Operation must be in Cleanup Started before completion.")
        completion_time = _utc_datetime(completion.completed_at)
        if completion_time > datetime.now(timezone.utc):
            raise ValueError("Completion date cannot be in the future.")
        evidence = await CleanupService.list_evidence(operation_id)
        if not any(item["evidence_type"] in {"AFTER_PHOTO", "INSPECTION_NOTE", "SUPPORTING_EVIDENCE"} for item in evidence):
            raise ValueError("Submit after-cleanup or inspection evidence before completion.")
        if completion.quantity_classification == "INDEPENDENTLY_VERIFIED":
            if not any(
                item["evidence_id"] == completion.verification_evidence_id
                and item["evidence_type"] in {"AFTER_PHOTO", "SUPPORTING_EVIDENCE"}
                and item.get("verification_status") == "VERIFIED"
                for item in evidence
            ):
                raise ValueError("Independent quantity verification must reference verified evidence for this operation.")
        now = datetime.now(timezone.utc)
        completion_data = completion.model_dump()
        completion_data["completed_at"] = completion_time
        result = await db_client.db[OPERATION_COLLECTION].update_one(
            {"operation_id": operation_id, "status": "CLEANUP_STARTED"},
            {
                "$set": {
                    "status": "COMPLETED",
                    "completion": completion_data,
                    "updated_at": now,
                },
                "$unset": {"active_recommendation_key": ""},
                "$push": {
                    "status_history": {
                        "status": "COMPLETED",
                        "changed_at": now,
                        "changed_by": actor_id,
                        "reason": "Completion details and supporting evidence recorded.",
                    },
                    "audit_history": {
                        "event": "COMPLETED",
                        "at": now,
                        "actor_id": actor_id,
                        "completion": completion_data,
                    },
                },
            },
        )
        if not result.matched_count:
            raise ValueError("Operation changed during completion; reload and retry.")
        return await CleanupService.get_operation(operation_id)

    @staticmethod
    async def get_analytics() -> Dict[str, Any]:
        collection = db_client.db[OPERATION_COLLECTION]
        cursor = collection.find(
            {"status": "COMPLETED"}, {"_id": 0, "completion": 1}
        ).limit(10000)
        operations = await cursor.to_list(length=10000)
        grouped: Dict[tuple[str, str], float] = {}
        monthly_counts: Dict[str, int] = {}
        for operation in operations:
            completion = operation.get("completion") or {}
            completed_at = completion.get("completed_at")
            if isinstance(completed_at, datetime):
                month = _utc_datetime(completed_at).strftime("%Y-%m")
                monthly_counts[month] = monthly_counts.get(month, 0) + 1
            quantity = completion.get("waste_quantity")
            unit = completion.get("measurement_unit")
            classification = completion.get("quantity_classification")
            if quantity is None or not unit or not classification:
                continue
            key = (unit, classification)
            grouped[key] = grouped.get(key, 0.0) + float(quantity)
        quantity_totals = [
            {"measurement_unit": unit, "classification": classification, "total": round(total, 3)}
            for (unit, classification), total in sorted(grouped.items())
        ]
        return {
            "completed_operations": len(operations),
            "monthly_completed_operations": [
                {"month": month, "completed_operations": count}
                for month, count in sorted(monthly_counts.items())
            ],
            "quantities_by_unit_and_classification": quantity_totals,
            "interpretation": (
                "Recorded collection quantities are reported cleanup outputs; they do not prove "
                "that environmental pollution or ambient concentrations decreased."
            ),
        }
