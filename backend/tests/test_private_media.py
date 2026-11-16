from io import BytesIO

import pytest
from fastapi import UploadFile
from PIL import Image
from starlette.datastructures import Headers

from app.services.private_media import PrivateMediaError, PrivateMediaStore


def _upload(image_format="PNG", content_type="image/png", filename="../unsafe.png"):
    data = BytesIO()
    Image.new("RGB", (4, 3), (10, 20, 30)).save(data, format=image_format)
    return UploadFile(
        filename=filename,
        file=BytesIO(data.getvalue()),
        headers=Headers({"content-type": content_type}),
    )


@pytest.mark.asyncio
async def test_image_upload_is_sanitized_and_stored_outside_public_assets(tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.private_media.settings.PRIVATE_MEDIA_DIR", str(tmp_path))

    media = await PrivateMediaStore.store_image(_upload())
    path = PrivateMediaStore.path_for(media)

    assert path.parent == tmp_path
    assert path.name != "../unsafe.png"
    assert media["content_type"] == "image/png"
    assert media["sha256"]
    with Image.open(path) as stored:
        assert stored.size == (4, 3)
        assert not stored.info.get("exif")


@pytest.mark.asyncio
async def test_upload_rejects_mismatched_mime_and_invalid_image(tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.private_media.settings.PRIVATE_MEDIA_DIR", str(tmp_path))
    with pytest.raises(PrivateMediaError, match="does not match"):
        await PrivateMediaStore.store_image(_upload("PNG", "image/jpeg"))
    with pytest.raises(PrivateMediaError, match="invalid or unsafe"):
        await PrivateMediaStore.store_image(
            UploadFile(
                filename="payload.png",
                file=BytesIO(b"not an image"),
                headers=Headers({"content-type": "image/png"}),
            )
        )
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_upload_enforces_configured_size_and_storage_key_validation(tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.private_media.settings.PRIVATE_MEDIA_DIR", str(tmp_path))
    monkeypatch.setattr("app.services.private_media.settings.PRIVATE_MEDIA_MAX_BYTES", 1024)
    large = UploadFile(
        filename="large.png",
        file=BytesIO(b"x" * 1025),
        headers=Headers({"content-type": "image/png"}),
    )

    with pytest.raises(PrivateMediaError, match="size limit"):
        await PrivateMediaStore.store_image(large)
    with pytest.raises(PrivateMediaError, match="reference is invalid"):
        PrivateMediaStore.path_for({"storage_key": "../private", "extension": "png"})
