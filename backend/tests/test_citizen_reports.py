from datetime import datetime, timezone
from copy import deepcopy
from types import SimpleNamespace

import pytest

from app.services.citizen_report_service import CitizenReportService


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
        item = next(
            (item for item in self.documents if all(item.get(key) == value for key, value in query.items())),
            None,
        )
        return deepcopy(item) if item is not None else None

    async def insert_one(self, document):
        self.documents.append(dict(document))
        return SimpleNamespace(inserted_id=document.get("report_id") or document.get("media_id"))

    async def update_one(self, query, update):
        document = next(
            (item for item in self.documents if all(item.get(key) == value for key, value in query.items())),
            None,
        )
        if document is None:
            return SimpleNamespace(matched_count=0)
        document.update(update.get("$set", {}))
        for key, value in update.get("$push", {}).items():
            document.setdefault(key, []).append(value)
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
    def __init__(self):
        self.collections = {}

    def __getitem__(self, name):
        return self.collections.setdefault(name, _Collection())


@pytest.mark.asyncio
async def test_citizen_submission_is_pending_and_separate_from_observations(monkeypatch):
    database = _Database()
    monkeypatch.setattr("app.services.citizen_report_service.db_client.db", database)
    async def store_image(_upload):
        return _stored_media()

    monkeypatch.setattr(
        "app.services.citizen_report_service.PrivateMediaStore.store_image",
        store_image,
    )
    now = datetime.now(timezone.utc)
    report = await CitizenReportService.submit(
        category="PLASTIC_DEBRIS",
        description="Plastic fragments observed near the inlet.",
        latitude=10.5,
        longitude=20.5,
        observed_at=now,
        upload=object(),
        user_id="reporter-1",
    )

    assert report["status"] == "PENDING"
    assert report["submitted_by"] == "reporter-1"
    assert "pollution_observations" not in database.collections
    assert report["status_history"][0]["status"] == "PENDING"
    assert "not a verified pollution observation" in report["status_history"][0]["reason"]


@pytest.mark.asyncio
async def test_citizen_report_moderation_is_audited_and_terminal(monkeypatch):
    database = _Database()
    monkeypatch.setattr("app.services.citizen_report_service.db_client.db", database)
    collection = database["citizen_reports"]
    collection.documents.append({
        "report_id": "report-1",
        "status": "PENDING",
        "status_history": [],
        "audit_history": [],
    })

    under_review = await CitizenReportService.moderate(
        "report-1", "UNDER_REVIEW", "Checking the submitted evidence.", "admin-1"
    )
    verified = await CitizenReportService.moderate(
        "report-1", "VERIFIED", "Evidence reviewed by a moderator.", "admin-1"
    )

    assert under_review["status"] == "UNDER_REVIEW"
    assert verified["status"] == "VERIFIED"
    assert len(verified["status_history"]) == 2
    assert verified["audit_history"][-1]["event"] == "MODERATED"
    with pytest.raises(ValueError, match="Cannot change citizen report status"):
        await CitizenReportService.moderate(
            "report-1", "REJECTED", "Cannot change a terminal review.", "admin-1"
        )


@pytest.mark.asyncio
async def test_report_lists_and_photos_are_scoped_to_submitter_unless_admin(monkeypatch, tmp_path):
    database = _Database()
    monkeypatch.setattr("app.services.citizen_report_service.db_client.db", database)
    monkeypatch.setattr("app.services.citizen_report_service.PrivateMediaStore._root", lambda: tmp_path)
    path = tmp_path / f"{'a' * 32}.png"
    path.write_bytes(b"private")
    database["citizen_reports"].documents.extend([
        {"report_id": "mine", "submitted_by": "user-1", "media_id": "media-1"},
        {"report_id": "other", "submitted_by": "user-2", "media_id": "media-2"},
    ])
    database["private_media"].documents.extend([
        {
            "media_id": f"media-{suffix}",
            "parent_type": "citizen_report",
            "parent_id": report_id,
            "storage_key": "a" * 32,
            "extension": "png",
            "content_type": "image/png",
        }
        for suffix, report_id in ((1, "mine"), (2, "other"))
    ])

    mine = await CitizenReportService.list_reports(user_id="user-1", is_admin=False)
    own_photo = await CitizenReportService.get_photo("mine", "user-1", False)
    forbidden_photo = await CitizenReportService.get_photo("other", "user-1", False)
    admin = await CitizenReportService.list_reports(user_id="admin-1", is_admin=True)

    assert [item["report_id"] for item in mine["data"]] == ["mine"]
    assert own_photo["path"] == path
    assert forbidden_photo is None
    assert admin["total"] == 2


def _stored_media():
    return {
        "storage_key": "a" * 32,
        "content_type": "image/png",
        "extension": "png",
        "size_bytes": 100,
        "sha256": "b" * 64,
        "width": 10,
        "height": 10,
    }


@pytest.mark.asyncio
async def test_citizen_report_api_restricts_moderation_to_admin(authenticated_app):
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(
        transport=ASGITransport(app=authenticated_app),
        base_url="http://test",
    ) as client:
        response = await client.patch(
            "/api/citizen-reports/report-1/moderation",
            json={"status": "VERIFIED", "reason": "Evidence reviewed."},
        )

    assert response.status_code == 403
