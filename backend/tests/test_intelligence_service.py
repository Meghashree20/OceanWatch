from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from pymongo.errors import DuplicateKeyError

from app.schemas.intelligence import OrganizationCreate
from app.services.intelligence_service import IntelligenceService


class _MemoryCollection:
    def __init__(self):
        self.documents = []

    async def find_one(self, query, _projection=None):
        return next(
            (document for document in self.documents if all(document.get(key) == value for key, value in query.items())),
            None,
        )

    async def insert_one(self, document):
        if any(existing.get("event_key") == document.get("event_key") for existing in self.documents):
            raise DuplicateKeyError("duplicate event key")
        self.documents.append(dict(document))

    async def update_one(self, query, update):
        document = await self.find_one(query)
        if document is None:
            return SimpleNamespace(matched_count=0)
        document.update(update.get("$set", {}))
        for key, value in update.get("$push", {}).items():
            document.setdefault(key, []).append(value)
        return SimpleNamespace(matched_count=1)


class _MemoryDatabase:
    def __init__(self, collection):
        self.collection = collection

    def __getitem__(self, name):
        return self.collection.get(name, self.collection) if isinstance(self.collection, dict) else self.collection


def _trend(risk="HIGH", baseline=False):
    return {
        "location": {"latitude": 10.5, "longitude": 20.5, "cell_size_degrees": 1.0},
        "risk_level": risk,
        "trend_direction": "unknown" if not baseline else "increasing",
        "change_types": ["no_comparable_baseline"] if not baseline else ["newly_high_risk"],
        "comparison": {
            "recent_mean_pieces_m3": 12.0 if risk == "HIGH" else 2.0,
            "previous_mean_pieces_m3": 1.0 if baseline else None,
            "absolute_change_pieces_m3": 11.0 if baseline else None,
            "relative_change": 11.0 if baseline else None,
            "previous_risk_level": "MEDIUM" if baseline else None,
        },
        "evidence": {
            "recent_observation_count": 4,
            "recent_sampling_site_count": 2,
            "previous_observation_count": 3 if baseline else None,
            "previous_sampling_site_count": 2 if baseline else None,
            "recent_period": {"start": "2024-01-01", "end": "2024-03-31"},
            "previous_period": {"start": "2023-10-01", "end": "2024-01-01"},
            "frequency_adjustment": "mean of per-site means",
            "data_quality": "moderate",
            "baseline_available": baseline,
            "adjacent_previous_high_risk_cell": False,
        },
        "source": "observed NOAA microplastic measurements",
    }


@pytest.mark.asyncio
async def test_alert_upsert_is_idempotent_and_preserves_status_history(monkeypatch):
    collection = _MemoryCollection()
    monkeypatch.setattr("app.services.intelligence_service.db_client.db", _MemoryDatabase(collection))

    await IntelligenceService._sync_alerts([_trend()])
    await IntelligenceService._sync_alerts([_trend()])
    alert = collection.documents[0]

    assert len(collection.documents) == 1
    assert alert["status"] == "ACTIVE"
    assert len(alert["status_history"]) == 1
    assert len(alert["assessment_history"]) == 1
    assert alert["source"] == "observed NOAA microplastic measurements"
    assert alert["affected_area"]["type"] == "Polygon"


@pytest.mark.asyncio
async def test_measured_fall_resolves_and_recurrence_reopens_alert(monkeypatch):
    collection = _MemoryCollection()
    monkeypatch.setattr("app.services.intelligence_service.db_client.db", _MemoryDatabase(collection))
    await IntelligenceService._sync_alerts([_trend("HIGH", baseline=True)])
    alert = collection.documents[0]

    await IntelligenceService._sync_alerts([_trend("MEDIUM", baseline=True)])
    assert alert["status"] == "RESOLVED"
    assert alert["status_history"][-1]["reason"].startswith("Comparable observations")

    await IntelligenceService._sync_alerts([_trend("HIGH", baseline=True)])
    assert alert["status"] == "ACTIVE"
    assert [entry["status"] for entry in alert["status_history"]] == ["ACTIVE", "RESOLVED", "ACTIVE"]


@pytest.mark.asyncio
async def test_alert_status_transition_records_authenticated_actor(monkeypatch):
    collection = _MemoryCollection()
    monkeypatch.setattr("app.services.intelligence_service.db_client.db", _MemoryDatabase(collection))
    await IntelligenceService._sync_alerts([_trend()])
    alert = collection.documents[0]

    updated = await IntelligenceService.update_alert_status(alert["alert_id"], "ACKNOWLEDGED", "user-1")

    assert updated["status"] == "ACKNOWLEDGED"
    assert updated["responsible_user_id"] == "user-1"
    assert updated["status_history"][-1]["changed_by"] == "user-1"

    with pytest.raises(ValueError, match="cannot transition"):
        await IntelligenceService.update_alert_status(alert["alert_id"], "ACTIVE", "user-2")


@pytest.mark.asyncio
async def test_alert_status_compare_and_swap_preserves_concurrent_update(monkeypatch):
    collection = _MemoryCollection()
    monkeypatch.setattr("app.services.intelligence_service.db_client.db", _MemoryDatabase(collection))
    await IntelligenceService._sync_alerts([_trend()])
    alert = collection.documents[0]
    original_update_one = collection.update_one

    async def update_after_concurrent_change(query, update):
        alert["status"] = "UNDER_INVESTIGATION"
        return await original_update_one(query, update)

    monkeypatch.setattr(collection, "update_one", update_after_concurrent_change)
    with pytest.raises(ValueError, match="changed concurrently"):
        await IntelligenceService.update_alert_status(alert["alert_id"], "ACKNOWLEDGED", "user-1")
    assert alert["status"] == "UNDER_INVESTIGATION"


def test_organization_registration_requires_closed_valid_geojson_polygon():
    payload = {
        "name": "  Coastal Response Group ",
        "contact_email": "ops@example.org",
        "service_area": {
            "type": "Polygon",
            "coordinates": [[[1, 1], [2, 1], [2, 2], [1, 1]]],
        },
        "areas_served": [" Bay A ", "Bay A"],
    }
    organization = OrganizationCreate.model_validate(payload)

    assert organization.name == "Coastal Response Group"
    assert organization.areas_served == ["Bay A"]
    with pytest.raises(ValidationError, match="polygon ring"):
        OrganizationCreate.model_validate({
            **payload,
            "service_area": {"type": "Polygon", "coordinates": [[[1, 1], [2, 2]]]},
        })


def test_affected_area_is_bounded_cell_polygon():
    polygon = IntelligenceService._affected_area(_trend())
    ring = polygon["coordinates"][0]
    assert ring[0] == ring[-1]
    assert ring[0][0] == 20.0
    assert ring[0][1] == 10.0


@pytest.mark.asyncio
async def test_notification_requires_explicit_send_and_records_delivery(monkeypatch):
    alerts = _MemoryCollection()
    notifications = _MemoryCollection()
    alert = {
        "alert_id": "alert-1",
        "affected_area": IntelligenceService._affected_area(_trend()),
        "location": _trend()["location"],
        "source": _trend()["source"],
        "risk_level": "HIGH",
        "triggering_evidence": {
            "change_types": _trend()["change_types"],
            "comparison": _trend()["comparison"],
            "evidence": _trend()["evidence"],
        },
    }
    alerts.documents.append(alert)
    monkeypatch.setattr(
        "app.services.intelligence_service.db_client.db",
        _MemoryDatabase({"pollution_alerts": alerts, "organization_notifications": notifications}),
    )
    organization = {
        "organization_id": "org-1",
        "name": "Registered Response Group",
        "contact_email": "response@example.org",
        "verified": True,
        "email_notifications_enabled": True,
    }
    async def matching_organizations(_alert):
        return [organization]
    monkeypatch.setattr(
        IntelligenceService,
        "_organization_matches_alert",
        staticmethod(matching_organizations),
    )
    sent = []
    monkeypatch.setattr(
        IntelligenceService,
        "_send_email",
        staticmethod(lambda email, subject, body: sent.append((email, subject, body))),
    )
    monkeypatch.setattr("app.services.intelligence_service.settings.SMTP_HOST", "smtp.example.org")
    monkeypatch.setattr("app.services.intelligence_service.settings.SMTP_FROM_EMAIL", "alerts@example.org")

    result = await IntelligenceService.send_notification("alert-1", "org-1", "admin-1")

    assert result["delivery_status"] == "SENT"
    assert result["approved_by"] == "admin-1"
    assert result["recipient_email"] == "oceanwatch-test@example.com"
    assert result["intended_recipient_email"] == "response@example.org"
    assert result["test_mode"] is True
    assert sent[0][0] == "oceanwatch-test@example.com"
    assert sent[0][1].startswith("[TEST]")
    assert "TEST MODE" in sent[0][2]
    assert "not a future pollution forecast" in sent[0][2]
    with pytest.raises(ValueError, match="already has status SENT"):
        await IntelligenceService.send_notification("alert-1", "org-1", "admin-1")


def test_email_test_mode_fails_closed_without_a_configured_recipient(monkeypatch):
    monkeypatch.setattr("app.services.intelligence_service.settings.SMTP_TEST_MODE", True)
    monkeypatch.setattr("app.services.intelligence_service.settings.SMTP_TEST_RECIPIENT", None)
    with pytest.raises(RuntimeError, match="SMTP_TEST_RECIPIENT"):
        IntelligenceService._notification_delivery(
            "organization@example.org", "Alert", "Details"
        )


def test_email_sender_refuses_unapproved_address_in_test_mode():
    with pytest.raises(RuntimeError, match="only permits the configured test recipient"):
        IntelligenceService._send_email(
            "unapproved@example.org", "Test", "Test body"
        )


@pytest.mark.asyncio
async def test_stale_assessments_do_not_create_or_resolve_alerts(monkeypatch):
    async def get_trends():
        return {
            "trends": [_trend()],
            "data_freshness": {"status": "stale", "age_days": 120},
        }

    sync_calls = []

    async def sync_alerts(trends):
        sync_calls.append(trends)

    async def list_alerts(status, limit):
        return {"data": [], "total": 0}

    monkeypatch.setattr(IntelligenceService, "get_trends", staticmethod(get_trends))
    monkeypatch.setattr(IntelligenceService, "_sync_alerts", staticmethod(sync_alerts))
    monkeypatch.setattr(IntelligenceService, "list_alerts", staticmethod(list_alerts))
    monkeypatch.setattr("app.services.intelligence_service.settings.POLLUTION_DATA_FRESHNESS_MAX_DAYS", 90)

    result = await IntelligenceService.assess()

    assert sync_calls == []
    assert result["alert_generation"]["status"] == "suppressed_stale_data"
    assert result["alerts"]["total"] == 0


@pytest.mark.asyncio
async def test_fresh_assessment_updates_alerts(monkeypatch):
    async def get_trends():
        return {
            "trends": [_trend()],
            "data_freshness": {"status": "fresh", "age_days": 2},
        }

    sync_calls = []

    async def sync_alerts(trends):
        sync_calls.append(trends)

    async def list_alerts(status, limit):
        return {"data": [], "total": 0}

    monkeypatch.setattr(IntelligenceService, "get_trends", staticmethod(get_trends))
    monkeypatch.setattr(IntelligenceService, "_sync_alerts", staticmethod(sync_alerts))
    monkeypatch.setattr(IntelligenceService, "list_alerts", staticmethod(list_alerts))

    result = await IntelligenceService.assess()

    assert sync_calls == [[_trend()]]
    assert result["alert_generation"]["status"] == "refreshed"


@pytest.mark.asyncio
async def test_trend_query_excludes_future_observations(monkeypatch):
    class _Cursor:
        def sort(self, *_args):
            return self

        def limit(self, *_args):
            return self

        async def to_list(self, length):
            assert length == 1
            return []

    class _Collection:
        def find(self, query, _projection):
            self.query = query
            return _Cursor()

    collection = _Collection()

    class _Database:
        def __getitem__(self, _name):
            return collection

    monkeypatch.setattr("app.services.intelligence_service.db_client.db", _Database())
    await IntelligenceService.get_trends()

    date_filter = collection.query["sample_date"]
    assert date_filter["$lte"] <= datetime.now(timezone.utc)
