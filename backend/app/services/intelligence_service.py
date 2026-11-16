"""Measured trend assessments, alerts, and organization notifications."""

import asyncio
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
import hashlib
import json
import smtplib
import ssl
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.core.config import settings
from app.db.mongodb import db_client
from app.ml.pollution_trends import PollutionTrendConfig, analyze_pollution_trends
from pymongo.errors import DuplicateKeyError


OBSERVATION_COLLECTION = "pollution_observations"
ALERT_COLLECTION = "pollution_alerts"
ORGANIZATION_COLLECTION = "environmental_organizations"
NOTIFICATION_COLLECTION = "organization_notifications"
ACTIVE_STATUSES = {"ACTIVE", "ACKNOWLEDGED", "UNDER_INVESTIGATION"}
ALLOWED_STATUS_TRANSITIONS = {
    "ACTIVE": {"ACKNOWLEDGED", "UNDER_INVESTIGATION", "RESOLVED", "CLOSED"},
    "ACKNOWLEDGED": {"UNDER_INVESTIGATION", "RESOLVED", "CLOSED"},
    "UNDER_INVESTIGATION": {"ACKNOWLEDGED", "RESOLVED", "CLOSED"},
    "RESOLVED": {"CLOSED"},
    "CLOSED": set(),
}


class IntelligenceService:
    @staticmethod
    async def get_trends(window_days: Optional[int] = None) -> Dict[str, Any]:
        window = settings.POLLUTION_TREND_WINDOW_DAYS if window_days is None else window_days
        if window < 7 or window > 3650:
            raise ValueError("window_days must be between 7 and 3650.")

        as_of = datetime.now(timezone.utc)
        collection = db_client.db[OBSERVATION_COLLECTION]
        latest_cursor = collection.find(
            {"unit": "pieces/m3", "sample_date": {"$ne": None, "$lte": as_of}},
            {"_id": 0, "sample_date": 1},
        ).sort("sample_date", -1).limit(1)
        latest_records = await latest_cursor.to_list(length=1)
        if not latest_records:
            return analyze_pollution_trends([], PollutionTrendConfig(window_days=window))
        latest_date = latest_records[0]["sample_date"]
        start_date = latest_date - timedelta(days=window * 2)
        cursor = collection.find(
            {
                "unit": "pieces/m3",
                "sample_date": {"$gt": start_date, "$lte": latest_date},
            },
            {
                "_id": 0,
                "sample_date": 1,
                "latitude": 1,
                "longitude": 1,
                "measurement": 1,
                "unit": 1,
            },
        )
        records = await cursor.to_list(length=None)
        config = PollutionTrendConfig(window_days=window)
        return analyze_pollution_trends(records, config, reference_time=as_of)

    @staticmethod
    def _alert_key(trend: Dict[str, Any]) -> str:
        location = trend["location"]
        identity = (
            f"observed-noaa:{location['cell_size_degrees']}:"
            f"{location['latitude']}:{location['longitude']}"
        )
        return hashlib.sha256(identity.encode("utf-8")).hexdigest()

    @staticmethod
    def _affected_area(trend: Dict[str, Any]) -> Dict[str, Any]:
        location = trend["location"]
        half = float(location["cell_size_degrees"]) / 2
        latitude, longitude = float(location["latitude"]), float(location["longitude"])
        west, east = max(-180.0, longitude - half), min(180.0, longitude + half)
        south, north = max(-90.0, latitude - half), min(90.0, latitude + half)
        return {
            "type": "Polygon",
            "coordinates": [[
                [west, south], [east, south], [east, north],
                [west, north], [west, south],
            ]],
        }

    @staticmethod
    def _assessment_history_item(trend: Dict[str, Any], assessed_at: datetime) -> Dict[str, Any]:
        evidence = {
            "change_types": trend["change_types"],
            "comparison": trend["comparison"],
            "evidence": trend["evidence"],
        }
        fingerprint = hashlib.sha256(
            json.dumps(
                {"risk_level": trend["risk_level"], "evidence": evidence},
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            ).encode("utf-8")
        ).hexdigest()
        return {
            "fingerprint": fingerprint,
            "assessed_at": assessed_at,
            "risk_level": trend["risk_level"],
            "evidence": evidence,
        }

    @staticmethod
    async def _record_status_change(
        collection: Any,
        alert: Dict[str, Any],
        status: str,
        actor_id: str,
        reason: str,
    ) -> None:
        now = datetime.now(timezone.utc)
        result = await collection.update_one(
            {"alert_id": alert["alert_id"], "status": alert["status"]},
            {
                "$set": {
                    "status": status,
                    "last_updated_at": now,
                    "responsible_user_id": actor_id if status in {"ACKNOWLEDGED", "UNDER_INVESTIGATION"} else alert.get("responsible_user_id"),
                },
                "$push": {
                    "status_history": {
                        "status": status,
                        "changed_at": now,
                        "changed_by": actor_id,
                        "reason": reason,
                    }
                },
            },
        )
        if not result.matched_count:
            raise ValueError("Alert status changed concurrently; reload and retry.")

    @staticmethod
    async def _sync_alerts(trends: List[Dict[str, Any]]) -> None:
        collection = db_client.db[ALERT_COLLECTION]
        now = datetime.now(timezone.utc)
        for trend in trends:
            alert_key = IntelligenceService._alert_key(trend)
            existing = await collection.find_one({"event_key": alert_key}, {"_id": 0})
            current_high = trend["risk_level"] in {"HIGH", "CRITICAL"}
            assessment_item = IntelligenceService._assessment_history_item(trend, now)
            if current_high and existing is None:
                alert_id = uuid4().hex
                alert = {
                    "alert_id": alert_id,
                    "event_key": alert_key,
                    "location": trend["location"],
                    "affected_area": IntelligenceService._affected_area(trend),
                    "source": trend["source"],
                    "risk_level": trend["risk_level"],
                    "triggering_evidence": {
                        "change_types": trend["change_types"],
                        "comparison": trend["comparison"],
                        "evidence": trend["evidence"],
                    },
                    "evidence_fingerprint": assessment_item["fingerprint"],
                    "assessment_history": [assessment_item],
                    "status": "ACTIVE",
                    "created_at": now,
                    "last_updated_at": now,
                    "responsible_user_id": None,
                    "status_history": [{
                        "status": "ACTIVE",
                        "changed_at": now,
                        "changed_by": "system",
                        "reason": "Configured observed concentration threshold reached.",
                    }],
                }
                try:
                    await collection.insert_one(alert)
                except DuplicateKeyError:
                    existing = await collection.find_one({"event_key": alert_key}, {"_id": 0})
                else:
                    continue
            if existing is None:
                continue
            if current_high:
                now = datetime.now(timezone.utc)
                update: Dict[str, Any] = {
                    "risk_level": trend["risk_level"],
                    "location": trend["location"],
                    "affected_area": IntelligenceService._affected_area(trend),
                    "source": trend["source"],
                    "triggering_evidence": {
                        "change_types": trend["change_types"],
                        "comparison": trend["comparison"],
                        "evidence": trend["evidence"],
                    },
                    "last_updated_at": now,
                }
                update_query: Dict[str, Any] = {"$set": update}
                if existing.get("evidence_fingerprint") != assessment_item["fingerprint"]:
                    update["evidence_fingerprint"] = assessment_item["fingerprint"]
                    update_query["$push"] = {"assessment_history": assessment_item}
                if existing.get("status") in {"RESOLVED", "CLOSED"}:
                    update["status"] = "ACTIVE"
                    update_query.setdefault("$push", {})["status_history"] = {
                        "status": "ACTIVE",
                        "changed_at": now,
                        "changed_by": "system",
                        "reason": "Observed high risk recurred in a comparable window.",
                    }
                    await collection.update_one({"alert_id": existing["alert_id"]}, update_query)
                else:
                    await collection.update_one(
                        {"alert_id": existing["alert_id"]},
                        update_query,
                    )
            elif (
                trend["evidence"]["baseline_available"]
                and existing.get("status") in ACTIVE_STATUSES
            ):
                await IntelligenceService._record_status_change(
                    collection,
                    existing,
                    "RESOLVED",
                    "system",
                    "Comparable observations show risk below the configured high-risk threshold.",
                )

    @staticmethod
    async def assess() -> Dict[str, Any]:
        assessment = await IntelligenceService.get_trends()
        freshness = assessment.get("data_freshness", {})
        data_is_current = (
            freshness.get("age_days") is not None
            and freshness.get("age_days") <= settings.POLLUTION_DATA_FRESHNESS_MAX_DAYS
        )
        if data_is_current:
            await IntelligenceService._sync_alerts(assessment.get("trends", []))
            assessment["alert_generation"] = {
                "status": "refreshed",
                "max_data_age_days": settings.POLLUTION_DATA_FRESHNESS_MAX_DAYS,
            }
        else:
            assessment["alert_generation"] = {
                "status": "suppressed_stale_data",
                "max_data_age_days": settings.POLLUTION_DATA_FRESHNESS_MAX_DAYS,
                "reason": "Stale or unavailable observations cannot create or resolve alerts.",
            }
        assessment["alerts"] = await IntelligenceService.list_alerts(status=None, limit=100)
        return assessment

    @staticmethod
    async def list_alerts(status: Optional[str] = "ACTIVE", limit: int = 100) -> Dict[str, Any]:
        collection = db_client.db[ALERT_COLLECTION]
        query = {"status": status} if status else {}
        cursor = collection.find(query, {"_id": 0}).sort("last_updated_at", -1).limit(limit)
        data = await cursor.to_list(length=limit)
        return {"data": data, "total": await collection.count_documents(query)}

    @staticmethod
    async def update_alert_status(alert_id: str, status: str, actor_id: str) -> Optional[Dict[str, Any]]:
        collection = db_client.db[ALERT_COLLECTION]
        alert = await collection.find_one({"alert_id": alert_id}, {"_id": 0})
        if alert is None:
            return None
        old_status = alert["status"]
        if status != old_status:
            if status not in ALLOWED_STATUS_TRANSITIONS[old_status]:
                raise ValueError(f"Alert cannot transition from {old_status} to {status}.")
            await IntelligenceService._record_status_change(
                collection,
                alert,
                status,
                actor_id,
                "Status updated by an authenticated OceanWatch user.",
            )
        return await collection.find_one({"alert_id": alert_id}, {"_id": 0})

    @staticmethod
    async def list_organizations(include_unverified: bool = False) -> List[Dict[str, Any]]:
        query = {} if include_unverified else {"verified": True}
        cursor = db_client.db[ORGANIZATION_COLLECTION].find(query, {"_id": 0}).sort("name", 1)
        return await cursor.to_list(length=500)

    @staticmethod
    async def create_organization(payload: Dict[str, Any], actor_id: str) -> Dict[str, Any]:
        organization = {
            "organization_id": uuid4().hex,
            **payload,
            "contact_email": str(payload["contact_email"]).strip().lower(),
            "verified": False,
            "created_by": actor_id,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        try:
            await db_client.db[ORGANIZATION_COLLECTION].insert_one(organization)
        except DuplicateKeyError as exc:
            raise ValueError("An organization with this contact email is already registered.") from exc
        return {key: value for key, value in organization.items() if key != "_id"}

    @staticmethod
    async def verify_organization(organization_id: str, verified: bool) -> Optional[Dict[str, Any]]:
        collection = db_client.db[ORGANIZATION_COLLECTION]
        result = await collection.update_one(
            {"organization_id": organization_id},
            {"$set": {"verified": verified, "updated_at": datetime.now(timezone.utc)}},
        )
        if not result.matched_count:
            return None
        return await collection.find_one({"organization_id": organization_id}, {"_id": 0})

    @staticmethod
    async def _organization_matches_alert(alert: Dict[str, Any]) -> List[Dict[str, Any]]:
        cursor = db_client.db[ORGANIZATION_COLLECTION].find(
            {
                "verified": True,
                "email_notifications_enabled": True,
                "service_area": {
                    "$geoIntersects": {"$geometry": alert["affected_area"]}
                },
            },
            {"_id": 0},
        ).sort("name", 1)
        return await cursor.to_list(length=500)

    @staticmethod
    def _notification_content(alert: Dict[str, Any], organization: Dict[str, Any]) -> tuple[str, str]:
        subject = f"OceanWatch {alert['risk_level']} observed pollution warning"
        evidence = alert["triggering_evidence"]
        comparison = evidence["comparison"]
        body = (
            f"Hello {organization['name']},\n\n"
            f"OceanWatch has recorded a {alert['risk_level']} observed pollution-risk assessment "
            f"within your verified service area.\n\n"
            f"Source: {alert['source']}\n"
            f"Cell center: {alert['location']['latitude']}, {alert['location']['longitude']} "
            f"(cell size {alert['location']['cell_size_degrees']} degrees)\n"
            f"Recent site-balanced mean: {comparison['recent_mean_pieces_m3']} pieces/m3\n"
            f"Previous mean: {comparison['previous_mean_pieces_m3']} pieces/m3\n"
            f"Change types: {', '.join(evidence['change_types']) or 'none'}\n"
            f"Recent observations: {evidence['evidence']['recent_observation_count']}\n"
            f"Comparable baseline available: {evidence['evidence']['baseline_available']}\n\n"
            "This is an observation-based assessment, not a future pollution forecast. "
            "Please review the underlying evidence before planning a response."
        )
        return subject, body

    @staticmethod
    async def preview_notifications(alert_id: str) -> Dict[str, Any]:
        alert = await db_client.db[ALERT_COLLECTION].find_one({"alert_id": alert_id}, {"_id": 0})
        if alert is None:
            raise KeyError("Alert not found.")
        organizations = await IntelligenceService._organization_matches_alert(alert)
        suggestions = []
        for organization in organizations:
            subject, body = IntelligenceService._notification_content(alert, organization)
            delivery_recipient: Optional[str] = organization["contact_email"]
            if settings.SMTP_TEST_MODE:
                delivery_recipient = (
                    str(settings.SMTP_TEST_RECIPIENT)
                    if settings.SMTP_TEST_RECIPIENT
                    else None
                )
            suggestions.append({
                "organization_id": organization["organization_id"],
                "name": organization["name"],
                "contact_email": organization["contact_email"],
                "delivery_recipient_email": delivery_recipient,
                "test_mode": settings.SMTP_TEST_MODE,
                "areas_served": organization.get("areas_served", []),
                "subject": subject,
                "body": body,
            })
        return {"alert_id": alert_id, "data": suggestions, "total": len(suggestions)}

    @staticmethod
    def _notification_delivery(
        intended_recipient: str,
        subject: str,
        body: str,
    ) -> tuple[str, str, str]:
        if not settings.SMTP_TEST_MODE:
            raise RuntimeError("External organization email delivery is disabled.")
        if not settings.SMTP_TEST_RECIPIENT:
            raise RuntimeError("Set SMTP_TEST_RECIPIENT before enabling email delivery.")
        return (
            str(settings.SMTP_TEST_RECIPIENT),
            f"[TEST] {subject}",
            "TEST MODE: delivered only to the configured test recipient.\n\n" + body,
        )

    @staticmethod
    def _send_email(to_address: str, subject: str, body: str) -> None:
        if (
            not settings.SMTP_TEST_MODE
            or not settings.SMTP_TEST_RECIPIENT
            or to_address != str(settings.SMTP_TEST_RECIPIENT)
        ):
            raise RuntimeError("SMTP delivery only permits the configured test recipient.")
        if not settings.SMTP_HOST or not settings.SMTP_FROM_EMAIL:
            raise RuntimeError("Outbound email is not configured; set the SMTP provider environment variables.")
        message = EmailMessage()
        message["From"] = str(settings.SMTP_FROM_EMAIL)
        message["To"] = to_address
        message["Subject"] = subject
        message.set_content(body)
        if settings.SMTP_SECURITY == "ssl":
            with smtplib.SMTP_SSL(
                settings.SMTP_HOST,
                settings.SMTP_PORT,
                timeout=settings.SMTP_TIMEOUT_SECONDS,
                context=ssl.create_default_context(),
            ) as server:
                if settings.SMTP_USERNAME:
                    server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD or "")
                server.send_message(message)
        else:
            with smtplib.SMTP(
                settings.SMTP_HOST,
                settings.SMTP_PORT,
                timeout=settings.SMTP_TIMEOUT_SECONDS,
            ) as server:
                server.starttls(context=ssl.create_default_context())
                if settings.SMTP_USERNAME:
                    server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD or "")
                server.send_message(message)

    @staticmethod
    async def send_notification(
        alert_id: str,
        organization_id: str,
        actor_id: str,
    ) -> Dict[str, Any]:
        alert = await db_client.db[ALERT_COLLECTION].find_one({"alert_id": alert_id}, {"_id": 0})
        if alert is None:
            raise KeyError("Alert not found.")
        matches = await IntelligenceService._organization_matches_alert(alert)
        organization = next(
            (item for item in matches if item["organization_id"] == organization_id),
            None,
        )
        if organization is None:
            raise ValueError("Organization is not verified, notification-enabled, or within the affected service area.")
        notifications = db_client.db[NOTIFICATION_COLLECTION]
        existing = await notifications.find_one(
            {"alert_id": alert_id, "organization_id": organization_id},
            {"_id": 0},
        )
        if existing and existing["delivery_status"] in {"PENDING", "SENT", "ACKNOWLEDGED"}:
            raise ValueError(f"Notification already has status {existing['delivery_status']}.")
        now = datetime.now(timezone.utc)
        subject, body = IntelligenceService._notification_content(alert, organization)
        recipient, subject, body = IntelligenceService._notification_delivery(
            organization["contact_email"], subject, body
        )
        notification_id = existing["notification_id"] if existing else uuid4().hex
        if existing:
            claimed = await notifications.update_one(
                {
                    "notification_id": notification_id,
                    "delivery_status": "FAILED",
                },
                {"$set": {
                    "delivery_status": "PENDING",
                    "recipient_email": recipient,
                    "intended_recipient_email": organization["contact_email"],
                    "test_mode": settings.SMTP_TEST_MODE,
                    "subject": subject,
                    "updated_at": now,
                    "approved_by": actor_id,
                }},
            )
            if claimed.matched_count != 1:
                raise ValueError("Notification is already being processed or has been delivered.")
        else:
            try:
                await notifications.insert_one({
                    "notification_id": notification_id,
                    "alert_id": alert_id,
                    "organization_id": organization_id,
                    "recipient_email": recipient,
                    "intended_recipient_email": organization["contact_email"],
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
                raise ValueError("A notification for this alert and organization is already recorded.") from exc
        try:
            await asyncio.to_thread(
                IntelligenceService._send_email,
                recipient,
                subject,
                body,
            )
        except Exception as exc:
            await notifications.update_one(
                {"notification_id": notification_id},
                {"$set": {
                    "delivery_status": "FAILED",
                    "delivery_error": type(exc).__name__,
                    "updated_at": datetime.now(timezone.utc),
                }},
            )
            raise RuntimeError("Email provider failed to send the approved notification.") from exc
        await notifications.update_one(
            {"notification_id": notification_id},
            {"$set": {
                "delivery_status": "SENT",
                "sent_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                "delivery_error": None,
            }},
        )
        return await notifications.find_one({"notification_id": notification_id}, {"_id": 0})

    @staticmethod
    async def acknowledge_notification(notification_id: str, actor_id: str) -> Optional[Dict[str, Any]]:
        collection = db_client.db[NOTIFICATION_COLLECTION]
        result = await collection.update_one(
            {
                "notification_id": notification_id,
                "delivery_status": "SENT",
            },
            {"$set": {
                "delivery_status": "ACKNOWLEDGED",
                "acknowledged_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                "acknowledged_by": actor_id,
            }},
        )
        if not result.matched_count:
            return None
        return await collection.find_one({"notification_id": notification_id}, {"_id": 0})

    @staticmethod
    async def list_notifications(alert_id: str) -> Dict[str, Any]:
        collection = db_client.db[NOTIFICATION_COLLECTION]
        cursor = collection.find({"alert_id": alert_id}, {"_id": 0}).sort("created_at", -1)
        data = await cursor.to_list(length=500)
        return {"data": data, "total": len(data)}
