"""CPU-only inference for the MARIDA U-Net segmentation model."""

from __future__ import annotations

import logging
from collections.abc import Mapping
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
    ) -> None:
        self.device = torch.device(device)
        self.input_bands = input_bands
        self.output_classes = output_classes
        self.model_path = Path(model_path)

        if not self.model_path.is_file():
            raise FileNotFoundError(f"U-Net model checkpoint not found at: {self.model_path}")

        logger.info(f"Loading MARIDA U-Net from {self.model_path} onto device={self.device}...")
        self.model = UNet(
            input_bands=input_bands,
            output_classes=output_classes,
            hidden_channels=hidden_channels,
        ).to(self.device)

        checkpoint = torch.load(
            self.model_path,
            map_location=self.device,
            weights_only=True,
        )
        state_dict = self._state_dict_from_checkpoint(checkpoint)
        self.model.load_state_dict(state_dict)
        self.model.eval()
        logger.info("MARIDA U-Net loaded and set to eval mode successfully.")

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
        padded_height = max(32, ((height + 15) // 16) * 16)
        padded_width = max(32, ((width + 15) // 16) * 16)
        pad_bottom = padded_height - height
        pad_right = padded_width - width
        if pad_bottom or pad_right:
            image = torch.nn.functional.pad(image, (0, pad_right, 0, pad_bottom), mode="replicate")

        logits = self.model(image.to(device=self.device, dtype=torch.float32))
        return logits.argmax(dim=1).squeeze(0)[:height, :width]

    __call__ = predict
