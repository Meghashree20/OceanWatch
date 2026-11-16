from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.schemas.cleanup import CleanupOperationCompletion
from app.services.cleanup_service import CleanupService
from app.services.recommendation_service import RecommendationService


class _Cursor:
    def __init__(self, documents):
        self.documents = list(documents)

    def sort(self, key, direction=1):
        self.documents.sort(key=lambda item: item.get(key) or "", reverse=direction < 0)
        return self

    def skip(self, amount):
        self.documents = self.documents[amount:]
        return self

    def limit(self, amount):
        self.documents = self.documents[:amount]
        return self

    async def to_list(self, length):
        return self.documents[:length]


class _Collection:
    def __init__(self, documents=None):
        self.documents = list(documents or [])

    async def find_one(self, query, _projection=None):
        return next(
            (
                item for item in self.documents
                if all(
                    item.get(key) in value["$in"] if isinstance(value, dict) and "$in" in value
                    else item.get(key) == value
                    for key, value in query.items()
                )
            ),
            None,
        )

    async def insert_one(self, document):
        self.documents.append(dict(document))
        return SimpleNamespace(inserted_id=document.get("operation_id"))

    async def update_one(self, query, update):
        document = await self.find_one(query)
        if document is None:
            return SimpleNamespace(matched_count=0)
        document.update(update.get("$set", {}))
        for key, value in update.get("$push", {}).items():
            document.setdefault(key, []).append(value)
        for key in update.get("$unset", {}):
            document.pop(key, None)
        return SimpleNamespace(matched_count=1)

    def find(self, query, _projection=None):
        return _Cursor([
            item for item in self.documents
            if all(item.get(key) == value for key, value in query.items())
        ])

    async def count_documents(self, query):
        return len([
            item for item in self.documents
            if all(item.get(key) == value for key, value in query.items())
        ])


class _Database:
    def __init__(self, collections):
        self.collections = collections

    def __getitem__(self, name):
        return self.collections.setdefault(name, _Collection())


def _operation(status="PLANNED"):
    return {
        "operation_id": "operation-1",
        "status": status,
        "assigned_organization_id": "org-1" if status != "PLANNED" else None,
        "location": {"latitude": 10.5, "longitude": 20.5},
        "status_history": [],
        "audit_history": [],
    }


@pytest.mark.asyncio
async def test_operation_creation_snapshots_only_a_current_recommendation(monkeypatch):
    collection = _Collection()
    monkeypatch.setattr(
        "app.services.cleanup_service.db_client.db",
        _Database({"cleanup_operations": collection}),
    )
    recommendation = {
        "recommendation_id": "a" * 64,
        "location": {"latitude": 10.5, "longitude": 20.5},
        "evidence": {"active_alert": {"alert_id": "alert-1"}},
    }

    async def current_recommendations(**_kwargs):
        return {"data": [recommendation], "total": 1}

    monkeypatch.setattr(
        RecommendationService,
        "get_cleanup_recommendations",
        staticmethod(current_recommendations),
    )

    operation = await CleanupService.create_operation(
        "a" * 64, None, "admin-1"
    )

    assert operation["status"] == "PLANNED"
    assert operation["recommendation_snapshot"] == recommendation
    assert operation["alert_id"] == "alert-1"
    assert operation["status_history"][0]["changed_by"] == "admin-1"


@pytest.mark.asyncio
async def test_notification_listing_exposes_safe_server_delivery_policy(monkeypatch):
    collection = _Collection()
    monkeypatch.setattr(
        "app.services.cleanup_service.db_client.db",
        _Database({"cleanup_operation_notifications": collection}),
    )
    monkeypatch.setattr("app.services.cleanup_service.settings.SMTP_TEST_MODE", True)
    monkeypatch.setattr(
        "app.services.cleanup_service.settings.SMTP_TEST_RECIPIENT",
        "oceanwatch-test@example.com",
    )

    result = await CleanupService.list_notifications("operation-1")

    assert result["data"] == []
    assert result["test_mode"] is True
    assert result["delivery_recipient_email"] == "oceanwatch-test@example.com"


@pytest.mark.asyncio
async def test_active_operation_creation_is_idempotent_and_cancelled_recommendation_can_be_reopened(monkeypatch):
    collection = _Collection()
    monkeypatch.setattr(
        "app.services.cleanup_service.db_client.db",
        _Database({"cleanup_operations": collection}),
    )
    recommendation = {
        "recommendation_id": "b" * 64,
        "location": {"latitude": 10.5, "longitude": 20.5},
        "evidence": {},
    }

    async def current_recommendations(**_kwargs):
        return {"data": [recommendation], "total": 1}

    monkeypatch.setattr(
        RecommendationService,
        "get_cleanup_recommendations",
        staticmethod(current_recommendations),
    )

    first = await CleanupService.create_operation("b" * 64, None, "admin-1")
    duplicate = await CleanupService.create_operation("b" * 64, None, "admin-1")

    assert duplicate["operation_id"] == first["operation_id"]
    assert len(collection.documents) == 1
    cancelled = await CleanupService.update_status(
        first["operation_id"], "CANCELLED", "No response needed.", "admin-1"
    )
    assert cancelled["status"] == "CANCELLED"
    reopened = await CleanupService.create_operation("b" * 64, None, "admin-1")
    assert reopened["operation_id"] != first["operation_id"]
    assert len(collection.documents) == 2


@pytest.mark.asyncio
async def test_assignment_requires_verified_org_and_active_coordinator(monkeypatch):
    collection = _Collection([_operation()])
    monkeypatch.setattr(
        "app.services.cleanup_service.db_client.db",
        _Database({"cleanup_operations": collection}),
    )
    organization = {"organization_id": "org-1", "name": "Verified Group", "verified": True}
    coordinator = {"user_id": "admin-1", "full_name": "Coordinator"}

    async def get_org(_org_id, _location=None):
        return organization

    async def get_coordinator(_user_id):
        return coordinator

    monkeypatch.setattr(CleanupService, "_verified_organization", staticmethod(get_org))
    monkeypatch.setattr(CleanupService, "_active_coordinator", staticmethod(get_coordinator))

    result = await CleanupService.assign_operation(
        "operation-1", "org-1", None, None, "admin-1"
    )

    assert result["status"] == "ASSIGNED"
    assert result["assigned_organization_id"] == "org-1"
    assert result["responsible_coordinator_user_id"] == "admin-1"
    assert result["status_history"][-1]["status"] == "ASSIGNED"
    assert result["audit_history"][-1]["event"] == "ASSIGNED"


@pytest.mark.asyncio
async def test_status_transitions_are_guarded_and_audited(monkeypatch):
    collection = _Collection([_operation()])
    monkeypatch.setattr(
        "app.services.cleanup_service.db_client.db",
        _Database({"cleanup_operations": collection}),
    )

    with pytest.raises(ValueError, match="Assign a verified organization"):
        await CleanupService.update_status(
            "operation-1", "ASSIGNED", "assign response", "admin-1"
        )

    with pytest.raises(ValueError, match="completion endpoint"):
        await CleanupService.update_status(
            "operation-1", "COMPLETED", "finished", "admin-1"
        )

    operation = collection.documents[0]
    operation["assigned_organization_id"] = "org-1"
    await CleanupService.update_status(
        "operation-1", "ASSIGNED", "assign response", "admin-1"
    )
    result = await CleanupService.update_status(
        "operation-1", "CLEANUP_STARTED", "start collection", "admin-1"
    )

    assert result["status"] == "CLEANUP_STARTED"
    assert result["status_history"][-1]["changed_by"] == "admin-1"
    assert result["audit_history"][-1]["from_status"] == "ASSIGNED"


@pytest.mark.asyncio
async def test_evidence_records_are_audited_and_completion_requires_evidence(monkeypatch):
    operation = _operation("CLEANUP_STARTED")
    operations = _Collection([operation])
    evidence = _Collection()
    database = _Database({
        "cleanup_operations": operations,
        "cleanup_operation_evidence": evidence,
    })
    monkeypatch.setattr("app.services.cleanup_service.db_client.db", database)

    with pytest.raises(ValueError, match="evidence before completion"):
        await CleanupService.complete_operation(
            "operation-1",
            CleanupOperationCompletion(completed_at=datetime.now(timezone.utc)),
            "admin-1",
        )

    # Inspection notes are textual evidence and do not require a fabricated image.
    result = await CleanupService.add_evidence(
        "operation-1", "INSPECTION_NOTE", "Crew reports collected debris.", None, "admin-1"
    )
    assert result["evidence_type"] == "INSPECTION_NOTE"
    assert operations.documents[0]["audit_history"][-1]["event"] == "EVIDENCE_SUBMITTED"

    completion = CleanupOperationCompletion(
        completed_at=datetime.now(timezone.utc),
        waste_quantity=12.5,
        measurement_unit="kg",
        quantity_classification="REPORTED",
    )
    completed = await CleanupService.complete_operation("operation-1", completion, "admin-1")

    assert completed["status"] == "COMPLETED"
    assert completed["completion"]["waste_quantity"] == 12.5
    assert completed["completion"]["quantity_classification"] == "REPORTED"
    assert completed["status_history"][-1]["status"] == "COMPLETED"
    assert not any("pollution_decreased" in item for item in completed["audit_history"])


@pytest.mark.asyncio
async def test_evidence_verification_is_audited_and_independent_quantity_needs_verified_media(monkeypatch):
    operation = _operation("CLEANUP_STARTED")
    operations = _Collection([operation])
    evidence = _Collection([{
        "operation_id": "operation-1",
        "evidence_id": "evidence-1",
        "evidence_type": "AFTER_PHOTO",
        "media_id": "media-1",
        "verification_status": "PENDING",
        "verification_history": [],
    }])
    database = _Database({
        "cleanup_operations": operations,
        "cleanup_operation_evidence": evidence,
    })
    monkeypatch.setattr("app.services.cleanup_service.db_client.db", database)
    completion = CleanupOperationCompletion(
        completed_at=datetime.now(timezone.utc),
        waste_quantity=4,
        measurement_unit="kg",
        quantity_classification="INDEPENDENTLY_VERIFIED",
        verification_evidence_id="evidence-1",
        verifier_name="Independent Reviewer",
        verifier_organization="External Review Group",
    )

    with pytest.raises(ValueError, match="verified evidence"):
        await CleanupService.complete_operation("operation-1", completion, "admin-1")

    reviewed = await CleanupService.verify_evidence(
        "operation-1", "evidence-1", "VERIFIED", "Photo and receipt reviewed.", "admin-2"
    )
    assert reviewed["verification_status"] == "VERIFIED"
    assert reviewed["verification_history"][-1]["changed_by"] == "admin-2"
    assert operations.documents[0]["audit_history"][-1]["event"] == "EVIDENCE_REVIEWED"

    completed = await CleanupService.complete_operation("operation-1", completion, "admin-1")
    assert completed["completion"]["quantity_classification"] == "INDEPENDENTLY_VERIFIED"


def test_independently_verified_quantities_require_a_verifier_and_evidence():
    with pytest.raises(ValueError, match="require evidence and verifier"):
        CleanupOperationCompletion(
            completed_at=datetime.now(timezone.utc),
            waste_quantity=1,
            measurement_unit="kg",
            quantity_classification="INDEPENDENTLY_VERIFIED",
        )


@pytest.mark.asyncio
async def test_historical_analytics_keep_units_and_quantity_classes_separate(monkeypatch):
    collection = _Collection([
        {
            "status": "COMPLETED",
            "completion": {
                "completed_at": datetime(2024, 3, 10, tzinfo=timezone.utc),
                "waste_quantity": 3,
                "measurement_unit": "kg",
                "quantity_classification": "REPORTED",
            },
        },
        {
            "status": "COMPLETED",
            "completion": {
                "completed_at": datetime(2024, 3, 22, tzinfo=timezone.utc),
                "waste_quantity": 1,
                "measurement_unit": "tonnes",
                "quantity_classification": "ESTIMATED",
            },
        },
        {"status": "COMPLETED", "completion": None},
    ])
    monkeypatch.setattr(
        "app.services.cleanup_service.db_client.db",
        _Database({"cleanup_operations": collection}),
    )

    result = await CleanupService.get_analytics()

    assert result["completed_operations"] == 3
    assert len(result["quantities_by_unit_and_classification"]) == 2
    assert result["monthly_completed_operations"] == [
        {"month": "2024-03", "completed_operations": 2}
    ]
    assert "do not prove" in result["interpretation"]
