"""Private citizen pollution reports and their moderation lifecycle."""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

from app.db.mongodb import db_client
from app.services.private_media import PrivateMediaStore


COLLECTION = "citizen_reports"
MEDIA_COLLECTION = "private_media"
VALID_TRANSITIONS = {
    "PENDING": {"UNDER_REVIEW", "REJECTED"},
    "UNDER_REVIEW": {"VERIFIED", "REJECTED"},
    "VERIFIED": set(),
    "REJECTED": set(),
}


def _utc_datetime(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class CitizenReportService:
    @staticmethod
    async def submit(
        *,
        category: str,
        description: str,
        latitude: float,
        longitude: float,
        observed_at: datetime,
        upload: Any,
        user_id: str,
    ) -> Dict[str, Any]:
        observed_time = _utc_datetime(observed_at)
        now = datetime.now(timezone.utc)
        if observed_time > now:
            raise ValueError("Observation timestamp cannot be in the future.")

        media = await PrivateMediaStore.store_image(upload)
        report_id = uuid4().hex
        media_id = uuid4().hex
        try:
            await db_client.db[MEDIA_COLLECTION].insert_one({
                "media_id": media_id,
                "storage_key": media["storage_key"],
                "content_type": media["content_type"],
                "extension": media["extension"],
                "size_bytes": media["size_bytes"],
                "sha256": media["sha256"],
                "width": media["width"],
                "height": media["height"],
                "parent_type": "citizen_report",
                "parent_id": report_id,
                "uploaded_by": user_id,
                "created_at": now,
            })
            report = {
                "report_id": report_id,
                "category": category,
                "description": description.strip(),
                "location": {"latitude": latitude, "longitude": longitude},
                "observed_at": observed_time,
                "media_id": media_id,
                "submitted_by": user_id,
                "status": "PENDING",
                "created_at": now,
                "updated_at": now,
                "status_history": [{
                    "status": "PENDING",
                    "changed_at": now,
                    "changed_by": user_id,
                    "reason": "Citizen report submitted; it is not a verified pollution observation.",
                }],
                "audit_history": [{
                    "event": "SUBMITTED",
                    "at": now,
                    "actor_id": user_id,
                }],
            }
            await db_client.db[COLLECTION].insert_one(report)
        except Exception:
            PrivateMediaStore.delete(media)
            await db_client.db[MEDIA_COLLECTION].delete_one({"media_id": media_id})
            raise
        return {key: value for key, value in report.items() if key != "_id"}

    @staticmethod
    async def list_reports(
        *,
        user_id: str,
        is_admin: bool,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Dict[str, Any]:
        query: Dict[str, Any] = {}
        if not is_admin:
            query["submitted_by"] = user_id
        if status:
            query["status"] = status
        collection = db_client.db[COLLECTION]
        cursor = collection.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit)
        return {
            "data": await cursor.to_list(length=limit),
            "total": await collection.count_documents(query),
            "skip": skip,
            "limit": limit,
        }

    @staticmethod
    async def moderate(
        report_id: str,
        status: str,
        reason: str,
        actor_id: str,
    ) -> Optional[Dict[str, Any]]:
        collection = db_client.db[COLLECTION]
        report = await collection.find_one({"report_id": report_id}, {"_id": 0})
        if report is None:
            return None
        if status not in VALID_TRANSITIONS.get(report["status"], set()):
            raise ValueError(f"Cannot change citizen report status from {report['status']} to {status}.")
        now = datetime.now(timezone.utc)
        result = await collection.update_one(
            {"report_id": report_id, "status": report["status"]},
            {
                "$set": {"status": status, "updated_at": now},
                "$push": {
                    "status_history": {
                        "status": status,
                        "changed_at": now,
                        "changed_by": actor_id,
                        "reason": reason,
                    },
                    "audit_history": {
                        "event": "MODERATED",
                        "at": now,
                        "actor_id": actor_id,
                        "status": status,
                        "reason": reason,
                    },
                },
            },
        )
        if not result.matched_count:
            raise ValueError("Citizen report changed during moderation; reload and retry.")
        return await collection.find_one({"report_id": report_id}, {"_id": 0})

    @staticmethod
    async def get_photo(report_id: str, user_id: str, is_admin: bool) -> Optional[Dict[str, Any]]:
        query: Dict[str, Any] = {"report_id": report_id}
        if not is_admin:
            query["submitted_by"] = user_id
        report = await db_client.db[COLLECTION].find_one(query, {"_id": 0})
        if report is None:
            return None
        media = await db_client.db[MEDIA_COLLECTION].find_one(
            {
                "media_id": report["media_id"],
                "parent_type": "citizen_report",
                "parent_id": report_id,
            },
            {"_id": 0},
        )
        if media is None:
            return None
        media["path"] = PrivateMediaStore.path_for(media)
        return media
