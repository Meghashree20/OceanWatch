import asyncio
from datetime import datetime, timedelta, timezone
from io import BytesIO
import os
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from motor.motor_asyncio import AsyncIOMotorClient
from PIL import Image
from pymongo.errors import DuplicateKeyError
from starlette.datastructures import Headers
from starlette.datastructures import UploadFile

from app.core.auth import require_active_user
from app.core.config import settings
from app.db.indexes import create_indexes
from app.db.mongodb import db_client
from app.main import app
from app.models.user import User
from app.schemas.cleanup import CleanupOperationCompletion
from app.schemas.intelligence import OrganizationCreate
from app.services.cleanup_service import CleanupService
from app.services.intelligence_service import IntelligenceService
from app.services.recommendation_service import RecommendationService


def _image_upload(filename: str) -> UploadFile:
    buffer = BytesIO()
    Image.new("RGB", (8, 8), (20, 40, 60)).save(buffer, format="PNG")
    return UploadFile(
        filename=filename,
        file=BytesIO(buffer.getvalue()),
        headers=Headers({"content-type": "image/png"}),
    )


def _alert_fixture(event_key: str) -> dict:
    return {
        "alert_id": uuid4().hex,
        "event_key": event_key,
        "location": {"latitude": 10.5, "longitude": 20.5, "cell_size_degrees": 1.0},
        "affected_area": {
            "type": "Polygon",
            "coordinates": [[[20, 10], [21, 10], [21, 11], [20, 11], [20, 10]]],
        },
        "source": "Stage 9 isolated test fixture; not environmental evidence",
        "risk_level": "HIGH",
        "triggering_evidence": {
            "change_types": ["test_fixture"],
            "comparison": {"recent_mean_pieces_m3": None, "previous_mean_pieces_m3": None},
            "evidence": {"recent_observation_count": 0, "baseline_available": False},
        },
        "evidence_fingerprint": "test-only",
        "assessment_history": [],
        "status": "ACTIVE",
        "created_at": datetime.now(timezone.utc),
        "last_updated_at": datetime.now(timezone.utc),
        "responsible_user_id": None,
        "status_history": [{
            "status": "ACTIVE",
            "changed_at": datetime.now(timezone.utc),
            "changed_by": "test-fixture",
            "reason": "Isolated integration-test fixture only.",
        }],
    }


@pytest.mark.asyncio
async def test_stage9_live_mongodb_workflows(tmp_path, monkeypatch):
    mongo_url = os.getenv("OCEANWATCH_TEST_MONGODB_URL")
    database_name = os.getenv("OCEANWATCH_TEST_MONGODB_DB_NAME")
    if not mongo_url or not database_name:
        pytest.skip("Set OCEANWATCH_TEST_MONGODB_URL and a unique Stage 9 test database name.")
    if not database_name.startswith("oceanwatch_stage9_test_"):
        pytest.fail("Refusing to run integration writes outside a uniquely named Stage 9 test database.")

    client = AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=3000)
    original_overrides = app.dependency_overrides.copy()
    created_test_database = False
    test_user = User(
        user_id="stage9-citizen",
        full_name="Stage 9 Test Citizen",
        email="citizen-stage9@example.invalid",
        password_hash="test-only",
        is_admin=False,
    )
    active_user = test_user
    app.dependency_overrides[require_active_user] = lambda: active_user

    try:
        await client.admin.command("ping")
        if database_name in await client.list_database_names():
            pytest.fail("The unique Stage 9 database name already exists; refusing to overwrite it.")

        created_test_database = True
        db_client.db = client[database_name]
        await create_indexes()
        monkeypatch.setattr(settings, "PRIVATE_MEDIA_DIR", str(tmp_path / "private-media"))

        indexes = await db_client.db["cleanup_operations"].index_information()
        assert indexes["unique_active_recommendation_operation"]["unique"] is True
        assert indexes["unique_active_recommendation_operation"]["sparse"] is True
        assert "service_area_2dsphere" in await db_client.db["environmental_organizations"].index_information()
        assert await db_client.db["pollution_observations"].count_documents({}) == 0

        alerts = db_client.db["pollution_alerts"]
        alert = _alert_fixture(f"stage9-{uuid4().hex}")
        await alerts.insert_one(alert)
        with pytest.raises(DuplicateKeyError):
            await alerts.insert_one({**alert, "alert_id": uuid4().hex})

        acknowledged = await IntelligenceService.update_alert_status(
            alert["alert_id"], "ACKNOWLEDGED", "stage9-admin"
        )
        assert acknowledged["status"] == "ACKNOWLEDGED"

        actual_recommendations = await RecommendationService.get_cleanup_recommendations()
        assert actual_recommendations["total"] == 1
        recommendation = actual_recommendations["data"][0]
        assert recommendation["action_type"] == "INSPECTION"
        assert recommendation["evidence"]["active_alert"]["alert_id"] == alert["alert_id"]
        assert await db_client.db["pollution_observations"].count_documents({}) == 0

        token = uuid4().hex
        organization_payload = OrganizationCreate(
            name=f"Stage 9 Temporary Test Organization {token[:8]}",
            contact_email=f"stage9-{token}@example.com",
            service_area={
                "type": "Polygon",
                "coordinates": [[[20, 10], [21, 10], [21, 11], [20, 11], [20, 10]]],
            },
            areas_served=["Stage 9 isolated test area"],
            email_notifications_enabled=True,
            acknowledgment_required=True,
        )
        organization = await IntelligenceService.create_organization(
            organization_payload.model_dump(), "stage9-admin"
        )
        assert organization["verified"] is False
        with pytest.raises(ValueError, match="already registered"):
            await IntelligenceService.create_organization(
                organization_payload.model_dump(), "stage9-admin"
            )
        verified_org = await IntelligenceService.verify_organization(
            organization["organization_id"], True
        )
        assert verified_org["verified"] is True

        await db_client.db["users"].insert_one({
            "user_id": "stage9-coordinator",
            "full_name": "Stage 9 Test Coordinator",
            "email": f"coordinator-{token}@example.invalid",
            "password_hash": "test-only",
            "is_active": True,
            "is_admin": True,
        })

        created_operations = await asyncio.gather(
            CleanupService.create_operation(recommendation["recommendation_id"], None, "stage9-admin"),
            CleanupService.create_operation(recommendation["recommendation_id"], None, "stage9-admin"),
        )
        operation = created_operations[0]
        assert created_operations[1]["operation_id"] == operation["operation_id"]
        assert "_id" not in operation
        assert await db_client.db["cleanup_operations"].count_documents(
            {"recommendation_id": recommendation["recommendation_id"]}
        ) == 1
        assert operation["alert_id"] == alert["alert_id"]

        concurrent = await asyncio.gather(
            IntelligenceService.update_alert_status(
                alert["alert_id"], "UNDER_INVESTIGATION", "stage9-admin-a"
            ),
            IntelligenceService.update_alert_status(
                alert["alert_id"], "CLOSED", "stage9-admin-b"
            ),
            return_exceptions=True,
        )
        assert sum(not isinstance(item, Exception) for item in concurrent) == 1
        assert sum(isinstance(item, ValueError) for item in concurrent) == 1
        persisted_alert = await alerts.find_one({"alert_id": alert["alert_id"]}, {"_id": 0})
        assert len(persisted_alert["status_history"]) == 3

        scheduled_at = datetime.now(timezone.utc) + timedelta(days=1)
        assigned = await CleanupService.assign_operation(
            operation["operation_id"],
            organization["organization_id"],
            "stage9-coordinator",
            scheduled_at,
            "stage9-admin",
        )
        assert assigned["status"] == "ASSIGNED"
        assert assigned["assigned_organization_id"] == organization["organization_id"]

        def fail_test_delivery(*_args):
            raise RuntimeError("Stage 9 simulated provider failure.")

        monkeypatch.setattr(IntelligenceService, "_send_email", staticmethod(fail_test_delivery))
        with pytest.raises(RuntimeError, match="provider failed"):
            await CleanupService.send_assignment_notification(
                operation["operation_id"], True, "stage9-admin"
            )
        failed_notification = await db_client.db["cleanup_operation_notifications"].find_one(
            {"operation_id": operation["operation_id"]}, {"_id": 0}
        )
        assert failed_notification["delivery_status"] == "FAILED"
        with pytest.raises(RuntimeError, match="provider failed"):
            await CleanupService.send_assignment_notification(
                operation["operation_id"], True, "stage9-admin"
            )
        retried_notification = await db_client.db["cleanup_operation_notifications"].find_one(
            {"operation_id": operation["operation_id"]}, {"_id": 0}
        )
        assert retried_notification["notification_id"] == failed_notification["notification_id"]
        assert await db_client.db["cleanup_operation_notifications"].count_documents({}) == 1

        monkeypatch.setattr(IntelligenceService, "_send_email", staticmethod(lambda *_args: None))
        sent_notification = await CleanupService.send_assignment_notification(
            operation["operation_id"], True, "stage9-admin"
        )
        assert sent_notification["delivery_status"] == "SENT"
        acknowledged_notification = await CleanupService.acknowledge_assignment(
            sent_notification["notification_id"], "stage9-admin"
        )
        assert acknowledged_notification["delivery_status"] == "ACKNOWLEDGED"

        await CleanupService.update_status(
            operation["operation_id"], "INSPECTION_SCHEDULED", "Inspection scheduled.", "stage9-admin"
        )
        await CleanupService.update_status(
            operation["operation_id"], "CLEANUP_STARTED", "Test workflow started.", "stage9-admin"
        )

        before = await CleanupService.add_evidence(
            operation["operation_id"], "BEFORE_PHOTO", "Stage 9 test fixture photo.", _image_upload("before.png"), "stage9-admin"
        )
        after = await CleanupService.add_evidence(
            operation["operation_id"], "AFTER_PHOTO", "Stage 9 test fixture photo.", _image_upload("after.png"), "stage9-admin"
        )
        evidence_media = await CleanupService.get_evidence_media(after["evidence_id"])
        assert evidence_media is not None
        assert evidence_media["media"]["path"].is_file()
        assert evidence_media["media"]["parent_id"] == operation["operation_id"]
        reviewed = await CleanupService.verify_evidence(
            operation["operation_id"], after["evidence_id"], "VERIFIED", "Stage 9 test fixture review.", "stage9-admin"
        )
        assert reviewed["verification_status"] == "VERIFIED"
        completion = CleanupOperationCompletion(
            completed_at=datetime.now(timezone.utc),
            waste_quantity=0,
            measurement_unit="kg",
            quantity_classification="INDEPENDENTLY_VERIFIED",
            verification_evidence_id=after["evidence_id"],
            verifier_name="Stage 9 Test Reviewer",
            verifier_organization="Stage 9 Temporary Test Organization",
        )
        completed = await CleanupService.complete_operation(
            operation["operation_id"], completion, "stage9-admin"
        )
        assert completed["status"] == "COMPLETED"
        assert [item["evidence_type"] for item in await CleanupService.list_evidence(operation["operation_id"])] == [
            "BEFORE_PHOTO", "AFTER_PHOTO"
        ]
        analytics = await CleanupService.get_analytics()
        assert analytics["completed_operations"] == 1
        assert "do not prove" in analytics["interpretation"]

        image_bytes = BytesIO()
        Image.new("RGB", (8, 8), (60, 40, 20)).save(image_bytes, format="PNG")
        active_user = test_user
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://stage9.test",
        ) as api:
            submitted = await api.post(
                "/api/citizen-reports",
                data={
                    "category": "PLASTIC_DEBRIS",
                    "description": "Stage 9 isolated test report, not an observation.",
                    "latitude": "10.5",
                    "longitude": "20.5",
                    "observed_at": datetime.now(timezone.utc).isoformat(),
                },
                files={"file": ("citizen.png", image_bytes.getvalue(), "image/png")},
            )
            assert submitted.status_code == 201
            report = submitted.json()
            assert report["status"] == "PENDING"
            assert "_id" not in report
            unsafe_upload = await api.post(
                "/api/citizen-reports",
                data={
                    "category": "PLASTIC_DEBRIS",
                    "description": "Unsafe test upload must be rejected.",
                    "latitude": "10.5",
                    "longitude": "20.5",
                    "observed_at": datetime.now(timezone.utc).isoformat(),
                },
                files={"file": ("unsafe.txt", b"not an image", "text/plain")},
            )
            assert unsafe_upload.status_code == 422
            assert await db_client.db["citizen_reports"].count_documents({}) == 1
            assert await db_client.db["pollution_observations"].count_documents({}) == 0
            denied_evidence = await api.get(f"/api/cleanup/evidence/{after['evidence_id']}/download")
            assert denied_evidence.status_code == 403
            owner_photo = await api.get(f"/api/citizen-reports/{report['report_id']}/photo")
            assert owner_photo.status_code == 200
            assert owner_photo.headers["cache-control"] == "private, no-store"
            active_user = User(
                user_id="stage9-other-citizen",
                full_name="Other Stage 9 Test Citizen",
                email="other-stage9@example.invalid",
                password_hash="test-only",
                is_admin=False,
            )
            private_photo = await api.get(f"/api/citizen-reports/{report['report_id']}/photo")
            assert private_photo.status_code == 404
            unauthorized = await api.get(f"/api/citizen-reports/{uuid4().hex}/photo")
            assert unauthorized.status_code == 404
            forbidden_moderation = await api.patch(
                f"/api/citizen-reports/{report['report_id']}/moderation",
                json={"status": "UNDER_REVIEW", "reason": "Should be forbidden."},
            )
            assert forbidden_moderation.status_code == 403

            active_user = User(
                user_id="stage9-admin",
                full_name="Stage 9 Test Administrator",
                email="admin-stage9@example.invalid",
                password_hash="test-only",
                is_admin=True,
            )
            under_review = await api.patch(
                f"/api/citizen-reports/{report['report_id']}/moderation",
                json={"status": "UNDER_REVIEW", "reason": "Reviewing test fixture."},
            )
            assert under_review.status_code == 200
            verified_report = await api.patch(
                f"/api/citizen-reports/{report['report_id']}/moderation",
                json={"status": "VERIFIED", "reason": "Test fixture review completed."},
            )
            assert verified_report.status_code == 200
            assert [item["status"] for item in verified_report.json()["status_history"]] == [
                "PENDING", "UNDER_REVIEW", "VERIFIED"
            ]
            admin_evidence = await api.get(f"/api/cleanup/evidence/{after['evidence_id']}/download")
            assert admin_evidence.status_code == 200

        assert await db_client.db["citizen_reports"].count_documents({"status": "VERIFIED"}) == 1
        assert before["verification_status"] == "PENDING"

    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(original_overrides)
        db_client.db = None
        if created_test_database:
            await client.drop_database(database_name)
        client.close()
