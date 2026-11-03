"""Inference for the MARIDA segmentation model."""

from __future__ import annotations

import hashlib
import json
import logging
import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import torch
from torch import Tensor

from app.ml.satellite.unet import UNet

logger = logging.getLogger(__name__)


class DebrisDetector:
    """Wrapper around trained MARIDA U-Net for pixel-level marine debris detection."""

    def __init__(
        self,
        model_path: str | Path = "models/model.pth",
        input_bands: int = 11,
        output_classes: int = 11,
        hidden_channels: int = 16,
        device: str = "cpu",
        class_names: Sequence[str] = (),
        band_order: Sequence[str] = (),
    ) -> None:
        self.device = torch.device(device)
        self.input_bands = input_bands
        self.output_classes = output_classes
        self.model_path = Path(model_path)

        if not self.model_path.is_file():
            raise FileNotFoundError(f"U-Net model checkpoint not found at: {self.model_path}")

        self.preprocessing = self._load_verified_metadata(
            class_names=class_names,
            band_order=band_order,
            hidden_channels=hidden_channels,
        )

        logger.info("Loading manifest-backed MARIDA U-Net from %s onto device=%s...", self.model_path, self.device)
        self.model = UNet(
            input_bands=input_bands,
            output_classes=output_classes,
            hidden_channels=hidden_channels,
        ).to(self.device)

        checkpoint = torch.load(self.model_path, map_location=self.device, weights_only=True)
        state_dict = self._state_dict_from_checkpoint(checkpoint)
        if not all(torch.isfinite(value).all() for value in state_dict.values() if value.is_floating_point()):
            raise ValueError("U-Net checkpoint contains non-finite tensor values.")
        self.model.load_state_dict(state_dict)
        self.model.eval()
        logger.info("Manifest-backed MARIDA U-Net loaded and set to eval mode successfully.")

    def _load_verified_metadata(
        self,
        class_names: Sequence[str],
        band_order: Sequence[str],
        hidden_channels: int,
    ) -> dict[str, Tensor]:
        metadata_path = self.model_path.with_name(f"{self.model_path.name}.metadata.json")
        if not metadata_path.is_file():
            raise ValueError(
                f"Checkpoint metadata is missing ({metadata_path.name}). A bare state dictionary cannot "
                "verify marine-plastic training, class order, or preprocessing. Supply a model metadata "
                "file backed by the original training and validation records."
            )

        try:
            with metadata_path.open(encoding="utf-8") as metadata_file:
                metadata = json.load(metadata_file)
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Checkpoint metadata file {metadata_path.name} is unreadable or invalid JSON.") from exc

        if (
            not isinstance(metadata, Mapping)
            or isinstance(metadata.get("format_version"), bool)
            or metadata.get("format_version") != 1
        ):
            raise ValueError("Checkpoint metadata must use the supported format_version 1.")
        if metadata.get("task") != "marine_plastic_segmentation":
            raise ValueError("Checkpoint metadata does not identify a marine-plastic segmentation task.")

        architecture = metadata.get("architecture")
        expected_architecture = {
            "name": "UNet",
            "input_bands": self.input_bands,
            "output_classes": self.output_classes,
            "hidden_channels": hidden_channels,
        }
        if not isinstance(architecture, Mapping) or any(
            architecture.get(key) != value for key, value in expected_architecture.items()
        ):
            raise ValueError("Checkpoint metadata architecture does not match the implemented U-Net.")
        if metadata.get("class_names") != list(class_names):
            raise ValueError("Checkpoint metadata class order does not match the MARIDA output taxonomy.")
        if metadata.get("band_order") != list(band_order):
            raise ValueError("Checkpoint metadata band order does not match the Sentinel-2 input order.")

        training = metadata.get("training")
        if (
            not isinstance(training, Mapping)
            or training.get("dataset") != "MARIDA"
            or not isinstance(training.get("provenance"), str)
            or not training["provenance"].strip()
            or not isinstance(training.get("validation_evidence"), str)
            or not training["validation_evidence"].strip()
        ):
            raise ValueError(
                "Checkpoint metadata must identify MARIDA training and provide training provenance "
                "and validation evidence."
            )

        checkpoint_hash = metadata.get("checkpoint_sha256")
        if not isinstance(checkpoint_hash, str) or len(checkpoint_hash) != 64:
            raise ValueError("Checkpoint metadata must contain the checkpoint SHA-256 digest.")
        digest = hashlib.sha256()
        with self.model_path.open("rb") as checkpoint_file:
            for block in iter(lambda: checkpoint_file.read(1024 * 1024), b""):
                digest.update(block)
        if digest.hexdigest() != checkpoint_hash.lower():
            raise ValueError("Checkpoint SHA-256 does not match its metadata.")

        preprocessing = metadata.get("preprocessing")
        if not isinstance(preprocessing, Mapping):
            raise ValueError("Checkpoint metadata must specify the training preprocessing parameters.")
        parameters: dict[str, Tensor] = {}
        for name in ("scale", "offset", "mean", "std"):
            values = preprocessing.get(name)
            if (
                not isinstance(values, list)
                or len(values) != self.input_bands
                or any(
                    isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not math.isfinite(value)
                    for value in values
                )
            ):
                raise ValueError(
                    f"Checkpoint preprocessing field '{name}' must contain {self.input_bands} finite numbers."
                )
            if name == "std" and any(value <= 0 for value in values):
                raise ValueError("Checkpoint preprocessing standard deviations must be greater than zero.")
            parameters[name] = torch.tensor(values, dtype=torch.float32, device=self.device).view(
                1, self.input_bands, 1, 1
            )
        return parameters

    @staticmethod
    def _state_dict_from_checkpoint(checkpoint: Any) -> Mapping[str, Tensor]:
        if isinstance(checkpoint, Mapping) and all(isinstance(k, str) for k in checkpoint):
            for key in ("state_dict", "model_state_dict"):
                nested = checkpoint.get(key)
                if isinstance(nested, Mapping):
                    checkpoint = nested
                    break
        if not isinstance(checkpoint, Mapping) or not checkpoint:
            raise TypeError("Model checkpoint must contain a non-empty state dictionary.")
        if not all(isinstance(k, str) and isinstance(v, Tensor) for k, v in checkpoint.items()):
            raise TypeError("Model checkpoint contains invalid state dictionary values.")
        return checkpoint

    @torch.inference_mode()
    def predict(self, image: Tensor) -> Tensor:
        """Run forward inference on 11-band imagery tensor and return 2D class mask."""
        if image.ndim == 3:
            image = image.unsqueeze(0)
        if image.ndim != 4 or image.shape[0] != 1 or image.shape[1] != self.input_bands:
            raise ValueError(
                f"Image tensor must have shape ({self.input_bands}, H, W) or (1, {self.input_bands}, H, W). "
                f"Got shape {tuple(image.shape)}."
            )
        height, width = image.shape[-2:]
        image = image.to(device=self.device, dtype=torch.float32)
        image = torch.where(torch.isfinite(image), image, self.preprocessing["mean"])

        padded_height = max(32, ((height + 15) // 16) * 16)
        padded_width = max(32, ((width + 15) // 16) * 16)
        pad_bottom = padded_height - height
        pad_right = padded_width - width
        if pad_bottom or pad_right:
            image = torch.nn.functional.pad(image, (0, pad_right, 0, pad_bottom), mode="replicate")

        image = (
            (image * self.preprocessing["scale"] + self.preprocessing["offset"] - self.preprocessing["mean"])
            / self.preprocessing["std"]
        )
        logits = self.model(image)
        return logits.argmax(dim=1).squeeze(0)[:height, :width]

    __call__ = predict
