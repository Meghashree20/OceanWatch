"""Sanitize and store private user-submitted images."""

from __future__ import annotations

from io import BytesIO
import hashlib
import re
from pathlib import Path
from typing import Any, Dict
from uuid import uuid4

from fastapi import UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.config import settings


CONTENT_TYPES = {"JPEG": ("image/jpeg", "jpg"), "PNG": ("image/png", "png")}


class PrivateMediaError(ValueError):
    """Raised when an uploaded image is unsupported or invalid."""


class PrivateMediaStore:
    @staticmethod
    def _root() -> Path:
        configured = Path(settings.PRIVATE_MEDIA_DIR)
        root = configured if configured.is_absolute() else Path(__file__).resolve().parents[2] / configured
        return root.resolve()

    @staticmethod
    async def store_image(upload: UploadFile) -> Dict[str, Any]:
        if upload.content_type not in {"image/jpeg", "image/png"}:
            raise PrivateMediaError("Only JPEG and PNG images are accepted.")
        raw = await upload.read(settings.PRIVATE_MEDIA_MAX_BYTES + 1)
        if not raw:
            raise PrivateMediaError("The uploaded image is empty.")
        if len(raw) > settings.PRIVATE_MEDIA_MAX_BYTES:
            raise PrivateMediaError("The uploaded image exceeds the configured size limit.")

        try:
            with Image.open(BytesIO(raw)) as source:
                image_format = source.format
                width, height = source.size
                if image_format not in CONTENT_TYPES:
                    raise PrivateMediaError("Only JPEG and PNG image content is accepted.")
                expected_type, extension = CONTENT_TYPES[image_format]
                if upload.content_type != expected_type:
                    raise PrivateMediaError("Image content does not match the declared content type.")
                if width <= 0 or height <= 0 or width * height > settings.PRIVATE_MEDIA_MAX_PIXELS:
                    raise PrivateMediaError("Image dimensions exceed the configured pixel limit.")
                source.verify()
            with Image.open(BytesIO(raw)) as source:
                oriented = ImageOps.exif_transpose(source)
                mode = "RGB" if image_format == "JPEG" else "RGBA"
                converted = oriented.convert(mode)
                sanitized = Image.new(mode, converted.size)
                sanitized.paste(converted)
                output = BytesIO()
                sanitized.save(output, format=image_format, optimize=True)
                encoded = output.getvalue()
                if len(encoded) > settings.PRIVATE_MEDIA_MAX_BYTES:
                    raise PrivateMediaError("Sanitized image exceeds the configured size limit.")
        except PrivateMediaError:
            raise
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
            raise PrivateMediaError("The uploaded image is invalid or unsafe to decode.") from exc

        storage_key = uuid4().hex
        root = PrivateMediaStore._root()
        root.mkdir(parents=True, exist_ok=True)
        target = (root / f"{storage_key}.{extension}").resolve()
        if target.parent != root:
            raise PrivateMediaError("Unable to resolve a safe media storage path.")
        with target.open("xb") as destination:
            destination.write(encoded)
        return {
            "storage_key": storage_key,
            "content_type": expected_type,
            "extension": extension,
            "size_bytes": len(encoded),
            "sha256": hashlib.sha256(encoded).hexdigest(),
            "width": width,
            "height": height,
        }

    @staticmethod
    def path_for(media: Dict[str, Any]) -> Path:
        storage_key = media.get("storage_key", "")
        extension = media.get("extension", "")
        if not re.fullmatch(r"[a-f0-9]{32}", storage_key) or extension not in {"jpg", "png"}:
            raise PrivateMediaError("Stored media reference is invalid.")
        root = PrivateMediaStore._root()
        path = (root / f"{storage_key}.{extension}").resolve()
        if path.parent != root:
            raise PrivateMediaError("Stored media path is invalid.")
        return path

    @staticmethod
    def delete(media: Dict[str, Any]) -> None:
        path = PrivateMediaStore.path_for(media)
        if path.exists():
            path.unlink()
