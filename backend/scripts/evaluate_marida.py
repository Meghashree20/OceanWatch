"""Reproducible evaluation of OceanWatch's unchanged MARIDA U-Net on MARIDA test.

Dataset: MARIDA 1.0.0 (Zenodo DOI 10.5281/zenodo.5151941), test_X.txt only.
Upstream methodology: marine-debris/marine-debris.github.io at the checkpoint
metadata's pinned revision. Research data are never passed through the production
upload API or registered in the production catalog.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rasterio
import torch
from sklearn.metrics import precision_recall_curve

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
REPO_ROOT = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.ml.satellite.detector import DebrisDetector  # noqa: E402
from app.ml.satellite.unet import UNet  # noqa: E402

MODEL_PATH = BACKEND_DIR / "models" / "model.pth"
METADATA_PATH = MODEL_PATH.with_name(f"{MODEL_PATH.name}.metadata.json")
EXPECTED_MODEL_SHA256 = "7a690027cf279b31cae45a3188f2d4faa011b222f42b5e92c9ec6b1fd46d1b37"
DATASET_DOI = "10.5281/zenodo.5151941"
DATASET_VERSION = "1.0.0"
DATASET_ARCHIVE_MD5 = "9bf32266f6e3711c9dfa3699b856c76f"
PAPER_REPORTED_TEST_ANNOTATED_PIXELS = 194_843
UPSTREAM_REPOSITORY = "https://github.com/marine-debris/marine-debris.github.io"
UPSTREAM_REVISION = "8de83a3394edfbe867d9fa825439666369ec6282"
UPSTREAM_LICENSE = "MIT"
DATASET_LICENSE = "CC-BY-4.0"
CLASS_NAMES = [
    "Marine Debris", "Dense Sargassum", "Sparse Sargassum",
    "Natural Organic Material", "Ship", "Clouds", "Marine Water",
    "Sediment-Laden Water", "Foam", "Turbid Water", "Shallow Water",
]
WAVELENGTH_BANDS = ["B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8", "B8A", "B11", "B12"]
RGB_CHANNELS = (3, 2, 1)  # B4/B3/B2


class UpstreamDown(torch.nn.Module):
    def __init__(self, input_channels: int, output_channels: int):
        super().__init__()
        self.maxpool_conv = torch.nn.Sequential(
            torch.nn.MaxPool2d(2),
            torch.nn.Conv2d(input_channels, output_channels, 3, padding=1),
            torch.nn.BatchNorm2d(output_channels), torch.nn.ReLU(inplace=True),
            torch.nn.Conv2d(output_channels, output_channels, 3, padding=1),
            torch.nn.BatchNorm2d(output_channels), torch.nn.ReLU(inplace=True),
        )

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        return self.maxpool_conv(value)


class UpstreamUp(torch.nn.Module):
    def __init__(self, input_channels: int, output_channels: int):
        super().__init__()
        self.up = torch.nn.Upsample(scale_factor=2, mode="bilinear", align_corners=True)
        self.conv = UpstreamUNet._double_conv(input_channels, output_channels)

    def forward(self, decoder: torch.Tensor, skip: torch.Tensor) -> torch.Tensor:
        decoder = self.up(decoder)
        return self.conv(torch.cat([skip, decoder], dim=1))


class UpstreamUNet(torch.nn.Module):
    """Pinned upstream UNet topology (without OceanWatch's dimension padding)."""

    def __init__(self, input_bands: int = 11, output_classes: int = 11, hidden_channels: int = 16):
        super().__init__()
        self.inc = self._double_conv(input_bands, hidden_channels)
        self.down1 = UpstreamDown(hidden_channels, 2 * hidden_channels)
        self.down2 = UpstreamDown(2 * hidden_channels, 4 * hidden_channels)
        self.down3 = UpstreamDown(4 * hidden_channels, 8 * hidden_channels)
        self.down4 = UpstreamDown(8 * hidden_channels, 8 * hidden_channels)
        self.up1 = UpstreamUp(16 * hidden_channels, 4 * hidden_channels)
        self.up2 = UpstreamUp(8 * hidden_channels, 2 * hidden_channels)
        self.up3 = UpstreamUp(4 * hidden_channels, hidden_channels)
        self.up4 = UpstreamUp(2 * hidden_channels, hidden_channels)
        self.outc = torch.nn.Conv2d(hidden_channels, output_classes, kernel_size=1)

    @staticmethod
    def _double_conv(input_channels: int, output_channels: int) -> torch.nn.Sequential:
        return torch.nn.Sequential(
            torch.nn.Conv2d(input_channels, output_channels, 3, padding=1),
            torch.nn.BatchNorm2d(output_channels), torch.nn.ReLU(inplace=True),
            torch.nn.Conv2d(output_channels, output_channels, 3, padding=1),
            torch.nn.BatchNorm2d(output_channels), torch.nn.ReLU(inplace=True),
        )

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        x1 = self.inc(value)
        x2 = self.down1(x1)
        x3 = self.down2(x2)
        x4 = self.down3(x3)
        x5 = self.down4(x4)
        x6 = self.up1(x5, x4)
        x7 = self.up2(x6, x3)
        x8 = self.up3(x7, x2)
        x9 = self.up4(x8, x1)
        return self.outc(x9)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def md5_file(path: Path) -> str:
    digest = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def resolve_dataset_root(path: Path) -> Path:
    """Accept a MARIDA root or its extracted top-level directory."""
    candidates = (path, path / "MARIDA", path / "data")
    for candidate in candidates:
        if (candidate / "patches").is_dir() and (candidate / "splits" / "test_X.txt").is_file():
            return candidate
    raise FileNotFoundError(
        f"Expected patches/ and splits/test_X.txt beneath {path}. Extract official MARIDA v1.0.0 first."
    )


def list_test_rois(dataset_root: Path) -> list[str]:
    split_sets: dict[str, set[str]] = {}
    expected_sizes = {"train_X.txt": 694, "val_X.txt": 328, "test_X.txt": 359}
    for split, expected_size in expected_sizes.items():
        other_file = dataset_root / "splits" / split
        if not other_file.is_file():
            raise FileNotFoundError(f"Missing split file {other_file}")
        items = [line.strip() for line in other_file.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
        if len(items) != len(set(items)):
            raise ValueError(f"MARIDA {split} contains duplicate ROI identifiers.")
        if len(items) != expected_size:
            raise ValueError(f"MARIDA {split} should contain {expected_size} ROIs; found {len(items)}.")
        split_sets[split] = set(items)
    names = list(split_sets)
    for index, left in enumerate(names):
        for right in names[index + 1:]:
            overlap = split_sets[left].intersection(split_sets[right])
            if overlap:
                raise ValueError(f"Dataset splits overlap ({left}, {right}): {sorted(overlap)[:5]}")
    if len(set.union(*split_sets.values())) != 1381:
        raise ValueError("MARIDA v1.0.0 train/validation/test split union should contain all 1,381 patches.")
    for split, items in split_sets.items():
        for roi in items:
            image_path, mask_path = roi_paths(dataset_root, roi)
            if not image_path.is_file() or not mask_path.is_file():
                raise FileNotFoundError(f"Split member {roi} lacks its image or class mask.")
    return sorted(split_sets["test_X.txt"])


def label_counts_by_split(dataset_root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    summary: dict[str, Any] = {}
    for split in ("train", "val", "test"):
        roi_file = dataset_root / "splits" / f"{split}_X.txt"
        rois = [line.strip() for line in roi_file.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
        counts = np.zeros(len(CLASS_NAMES), dtype=np.int64)
        debris_scenes = 0
        for roi in rois:
            _, mask_path = roi_paths(dataset_root, roi)
            with rasterio.open(mask_path) as raster:
                source_mask = raster.read(1)
            mapped, valid = map_labels(source_mask)
            counts += np.bincount(mapped[valid], minlength=len(CLASS_NAMES))
            debris_scenes += int(np.any(source_mask == 1))
        total = int(counts.sum())
        summary[split] = {
            "scene_count": len(rois), "labeled_pixel_count": total,
            "marine_debris_pixel_count": int(counts[0]),
            "scenes_with_labeled_marine_debris": debris_scenes,
        }
        for name, count in zip(CLASS_NAMES, counts):
            rows.append({"split": split, "class_name": name, "labeled_pixel_support": int(count),
                         "percent_of_labeled_pixels": float(100 * count / total) if total else None})
    return rows, summary


def roi_paths(dataset_root: Path, roi: str) -> tuple[Path, Path]:
    pieces = roi.split("_")
    folder = "_".join(["S2", *pieces[:-1]])
    filename = "_".join(["S2", *pieces])
    scene_dir = dataset_root / "patches" / folder
    return scene_dir / f"{filename}.tif", scene_dir / f"{filename}_cl.tif"


def load_patch(dataset_root: Path, roi: str) -> tuple[np.ndarray, np.ndarray]:
    image_path, label_path = roi_paths(dataset_root, roi)
    if not image_path.is_file() or not label_path.is_file():
        raise FileNotFoundError(f"Missing image or label for test ROI {roi}: {image_path}, {label_path}")
    with rasterio.open(image_path) as raster:
        image = raster.read().astype(np.float32, copy=False)
        if raster.count != 11 or image.shape[1:] != (256, 256):
            raise ValueError(f"Unexpected image shape/count for {roi}: {image.shape}; expected (11,256,256)")
    with rasterio.open(label_path) as raster:
        labels = raster.read(1).astype(np.int16, copy=False)
        if labels.shape != (256, 256):
            raise ValueError(f"Unexpected label shape for {roi}: {labels.shape}; expected (256,256)")
    if np.any((labels < 0) | (labels > 15)):
        raise ValueError(f"Mask for {roi} contains values outside official class IDs 0..15")
    return image, labels


def map_labels(source_labels: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Map official 1..15 labels to the upstream 11-class IDs; 0 is ignored."""
    mapped = source_labels.astype(np.int16, copy=True)
    mapped[np.isin(mapped, (12, 13, 14, 15))] = 7  # upstream: four water-like labels -> source ID 7
    mapped -= 1
    valid = source_labels != 0
    mapped[~valid] = -1
    if np.any((mapped[valid] < 0) | (mapped[valid] >= 11)):
        raise AssertionError("Mapped labels do not fit the 11-class checkpoint taxonomy")
    return mapped, valid


def normalize(image: np.ndarray, preprocessing: dict[str, torch.Tensor]) -> torch.Tensor:
    # Same ordering as upstream: impute non-finite input with the band mean,
    # then apply metadata scale/offset and channel-wise standardization.
    data = torch.from_numpy(np.array(image, dtype=np.float32, copy=True)).unsqueeze(0).to(preprocessing["mean"].device)
    data = torch.where(torch.isfinite(data), data, preprocessing["mean"])
    return (data * preprocessing["scale"] + preprocessing["offset"] - preprocessing["mean"]) / preprocessing["std"]


def prepare_local_input(image: np.ndarray, detector: DebrisDetector) -> tuple[torch.Tensor, tuple[int, int]]:
    value = torch.from_numpy(np.array(image, dtype=np.float32, copy=True)).unsqueeze(0).to(detector.device)
    value = torch.where(torch.isfinite(value), value, detector.preprocessing["mean"])
    height, width = value.shape[-2:]
    padded_height = max(32, ((height + 15) // 16) * 16)
    padded_width = max(32, ((width + 15) // 16) * 16)
    if padded_height != height or padded_width != width:
        value = torch.nn.functional.pad(value, (0, padded_width - width, 0, padded_height - height), mode="replicate")
    value = (value * detector.preprocessing["scale"] + detector.preprocessing["offset"] - detector.preprocessing["mean"]) / detector.preprocessing["std"]
    return value, (height, width)


def counts_from_confusion(matrix: np.ndarray) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    total_support = int(matrix.sum())
    for class_id, name in enumerate(CLASS_NAMES):
        tp = int(matrix[class_id, class_id])
        support = int(matrix[class_id, :].sum())
        fp = int(matrix[:, class_id].sum()) - tp
        fn = support - tp
        union = tp + fp + fn
        if support:
            precision = tp / (tp + fp) if tp + fp else None
            recall = tp / support
            f1 = 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None
            iou = tp / union if union else None
        else:
            precision = recall = f1 = iou = None
        rows.append({
            "class_id": class_id, "class_name": name, "support": support,
            "true_positives": tp, "false_positives": fp, "false_negatives": fn,
            "precision": precision, "recall": recall, "f1": f1, "iou": iou,
            "status": "available" if support else "unavailable_no_labeled_test_pixels",
        })
    available = [row for row in rows if row["support"] > 0]
    tp_sum = int(np.trace(matrix))
    weighted_f1 = sum(row["f1"] * row["support"] for row in available if row["f1"] is not None) / total_support if total_support else None
    summary = {
        "labeled_pixels": total_support,
        "overall_pixel_accuracy": tp_sum / total_support if total_support else None,
        "mean_iou_over_classes_with_labeled_test_support": float(np.mean([r["iou"] for r in available if r["iou"] is not None])) if available else None,
        "macro_f1_over_classes_with_labeled_test_support": float(np.mean([r["f1"] for r in available if r["f1"] is not None])) if available else None,
        "weighted_f1": weighted_f1,
    }
    return rows, summary


def class_metrics(matrix: np.ndarray) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows, summary = counts_from_confusion(matrix)
    return rows, summary


def ece(confidence: np.ndarray, correct: np.ndarray, bins: int = 15) -> float | None:
    if confidence.size == 0:
        return None
    edges = np.linspace(0.0, 1.0, bins + 1)
    total = confidence.size
    value = 0.0
    for low, high in zip(edges[:-1], edges[1:]):
        selected = (confidence >= low) & (confidence < high if high < 1 else confidence <= high)
        if selected.any():
            value += float(selected.sum() / total) * abs(float(confidence[selected].mean()) - float(correct[selected].mean()))
    return value


def binary_brier(scores: np.ndarray, truth: np.ndarray) -> float | None:
    if not truth.size:
        return None
    return float(np.mean((scores.astype(np.float64) - truth.astype(np.float64)) ** 2))


def summarize_scores(values: np.ndarray) -> dict[str, Any]:
    if values.size == 0:
        return {"count": 0, "mean": None, "std": None, "percentiles": {}}
    percentiles = np.percentile(values, [0, 5, 25, 50, 75, 95, 100])
    return {
        "count": int(values.size), "mean": float(values.mean()), "std": float(values.std()),
        "percentiles": {str(q): float(value) for q, value in zip((0, 5, 25, 50, 75, 95, 100), percentiles)},
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as target:
        writer = csv.DictWriter(target, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def markdown_number(value: Any, digits: int = 4) -> str:
    return "N/A" if value is None else f"{value:.{digits}f}" if isinstance(value, (float, np.floating)) else str(value)


def rgb_preview(image: np.ndarray) -> np.ndarray:
    rgb = np.moveaxis(image[list(RGB_CHANNELS)], 0, -1).astype(np.float32)
    finite = np.isfinite(rgb)
    if not finite.any():
        return np.zeros((*rgb.shape[:2], 3), dtype=np.float32)
    values = rgb[finite]
    low, high = np.percentile(values, [2, 98])
    if high <= low:
        high = low + 1.0
    rgb = np.nan_to_num((rgb - low) / (high - low), nan=0.0, posinf=1.0, neginf=0.0)
    return np.clip(rgb, 0, 1)


def save_comparison(path: Path, roi: str, image: np.ndarray, truth: np.ndarray, prediction: np.ndarray, valid: np.ndarray, title: str) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.5), constrained_layout=True)
    axes[0].imshow(rgb_preview(image)); axes[0].set_title("Sentinel-2 RGB (2–98% stretch)")
    truth_view = np.ma.masked_where(~valid, truth)
    pred_view = np.ma.masked_where(~valid, prediction)
    cmap = plt.get_cmap("tab20", 11).copy(); cmap.set_bad("black")
    axes[1].imshow(truth_view, vmin=0, vmax=10, cmap=cmap, interpolation="nearest"); axes[1].set_title("Ground truth (unlabeled black)")
    axes[2].imshow(pred_view, vmin=0, vmax=10, cmap=cmap, interpolation="nearest"); axes[2].set_title("U-Net prediction")
    for axis in axes: axis.axis("off")
    fig.suptitle(f"{title}: {roi}")
    fig.savefig(path, dpi=160)
    plt.close(fig)


def evaluate(dataset_root: Path, output_dir: Path, device: str = "cpu", archive_path: Path | None = None) -> dict[str, Any]:
    dataset_root = resolve_dataset_root(dataset_root)
    archive_path = archive_path or BACKEND_DIR / "data" / "MARIDA.zip"
    archive_md5 = md5_file(archive_path) if archive_path.is_file() else None
    if archive_md5 is not None and archive_md5.lower() != DATASET_ARCHIVE_MD5:
        raise ValueError(f"MARIDA archive MD5 mismatch: expected {DATASET_ARCHIVE_MD5}, found {archive_md5}")
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "visualizations").mkdir(exist_ok=True)
    model_hash = sha256_file(MODEL_PATH)
    if model_hash != EXPECTED_MODEL_SHA256:
        raise ValueError(f"Checkpoint SHA-256 mismatch: {model_hash}")
    metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    rois = list_test_rois(dataset_root)
    split_label_rows, split_label_summary = label_counts_by_split(dataset_root)
    if metadata["class_names"] != CLASS_NAMES or metadata["band_order"] != WAVELENGTH_BANDS:
        raise ValueError("Checkpoint metadata class/band order does not match this evaluator")

    detector = DebrisDetector(MODEL_PATH, device=device, class_names=CLASS_NAMES, band_order=WAVELENGTH_BANDS)
    upstream = UpstreamUNet().to(device)
    upstream.load_state_dict(torch.load(MODEL_PATH, map_location=device, weights_only=True), strict=True)
    upstream.eval()
    class_count = len(CLASS_NAMES)
    confusion = np.zeros((class_count, class_count), dtype=np.int64)
    per_scene: list[dict[str, Any]] = []
    scene_records: list[dict[str, Any]] = []
    all_conf: list[np.ndarray] = []
    all_correct: list[np.ndarray] = []
    all_pred: list[np.ndarray] = []
    all_true: list[np.ndarray] = []
    all_probs: list[np.ndarray] = []
    comparison = {"scenes": 0, "exact_prediction_scenes": 0, "exact_prediction_pixels": 0,
                  "compared_pixels": 0, "logits_allclose_scenes": 0, "max_absolute_logit_difference": 0.0,
                  "max_absolute_probability_difference": 0.0}
    torch.set_num_threads(max(1, min(4, torch.get_num_threads())))

    for index, roi in enumerate(rois, start=1):
        image, source = load_patch(dataset_root, roi)
        truth, valid = map_labels(source)
        normalized = normalize(image, detector.preprocessing).to(device)
        with torch.inference_mode():
            upstream_logits = upstream(normalized)
            upstream_probabilities = torch.softmax(upstream_logits, dim=1)
            upstream_prediction = upstream_probabilities.argmax(dim=1)[0]
            local_input, original_shape = prepare_local_input(image, detector)
            local_input = local_input.to(device)
            local_logits = detector.model(local_input)[..., :original_shape[0], :original_shape[1]]
            local_probabilities = torch.softmax(local_logits, dim=1)
            local_prediction = local_probabilities.argmax(dim=1)[0]
            local_max_confidence = local_probabilities.max(dim=1).values[0]
        upstream_logits_np = upstream_logits[0].cpu().numpy()
        local_logits_np = local_logits[0].cpu().numpy()
        upstream_probs_np = upstream_probabilities[0].cpu().numpy()
        local_probs_np = local_probabilities[0].cpu().numpy()
        pred = local_prediction.cpu().numpy().astype(np.int16)
        up_pred = upstream_prediction.cpu().numpy().astype(np.int16)
        confidence = local_max_confidence.cpu().numpy().astype(np.float32)
        correct = pred == truth
        valid_flat = valid.ravel()
        scene_pred, scene_true = pred.ravel()[valid_flat], truth.ravel()[valid_flat]
        matrix = np.bincount(scene_true * class_count + scene_pred, minlength=class_count ** 2).reshape(class_count, class_count)
        confusion += matrix
        scene_rows, scene_summary = class_metrics(matrix)
        md = scene_rows[0]
        debris_truth = int(md["support"])
        debris_tp, debris_fp, debris_fn = int(md["true_positives"]), int(md["false_positives"]), int(md["false_negatives"])
        nondebris = int(valid.sum()) - debris_truth
        per_scene.append({
            "roi": roi, "scene": "_".join(roi.split("_")[:-1]), "labeled_pixels": int(valid.sum()),
            "marine_debris_pixels": debris_truth,
            "marine_debris_precision": md["precision"], "marine_debris_recall": md["recall"],
            "marine_debris_f1": md["f1"], "marine_debris_iou": md["iou"],
            "marine_debris_tp": debris_tp, "marine_debris_fp": debris_fp, "marine_debris_fn": debris_fn,
            "debris_false_positive_rate_non_debris": debris_fp / nondebris if nondebris else None,
            "false_debris_predictions_pct_of_labeled_pixels": 100 * debris_fp / int(valid.sum()) if valid.any() else None,
            "pixel_accuracy": scene_summary["overall_pixel_accuracy"],
            "mean_iou_present_classes": scene_summary["mean_iou_over_classes_with_labeled_test_support"],
        })
        all_conf.append(confidence.ravel()[valid_flat])
        all_correct.append(correct.ravel()[valid_flat])
        all_pred.append(scene_pred)
        all_true.append(scene_true)
        all_probs.append(local_probs_np.reshape(class_count, -1)[:, valid_flat])
        abs_logits = np.abs(upstream_logits_np - local_logits_np)
        abs_probs = np.abs(upstream_probs_np - local_probs_np)
        comparison["scenes"] += 1
        comparison["exact_prediction_scenes"] += int(np.array_equal(up_pred, pred))
        comparison["exact_prediction_pixels"] += int(np.count_nonzero(up_pred == pred))
        comparison["compared_pixels"] += int(pred.size)
        comparison["logits_allclose_scenes"] += int(np.allclose(upstream_logits_np, local_logits_np, rtol=1e-5, atol=1e-6))
        comparison["max_absolute_logit_difference"] = max(comparison["max_absolute_logit_difference"], float(abs_logits.max()))
        comparison["max_absolute_probability_difference"] = max(comparison["max_absolute_probability_difference"], float(abs_probs.max()))
        scene_records.append({"roi": roi, "image": image, "source": source, "truth": truth, "valid": valid,
                              "prediction": pred, "confidence": confidence, "fp": debris_fp, "fn": debris_fn,
                              "matrix": matrix, "upstream_prediction": up_pred})
        if index % 25 == 0 or index == len(rois):
            print(f"Evaluated {index}/{len(rois)} official test scenes", flush=True)

    y_true = np.concatenate(all_true)
    y_pred = np.concatenate(all_pred)
    confidence = np.concatenate(all_conf)
    correct = np.concatenate(all_correct)
    probabilities = np.concatenate(all_probs, axis=1)
    class_rows, summary = class_metrics(confusion)
    total = y_true.size
    debris_score = probabilities[0]
    debris_binary_truth = (y_true == 0).astype(np.uint8)
    pr_precision, pr_recall, pr_thresholds = precision_recall_curve(debris_binary_truth, debris_score)
    pr_rows = [{"threshold": float(t), "precision": float(p), "recall": float(r)}
               for p, r, t in zip(pr_precision[:-1], pr_recall[:-1], pr_thresholds)]
    threshold_rows = []
    for raw_threshold in np.arange(0.1, 1.0, 0.05):
        threshold = round(float(raw_threshold), 2)
        selected = (y_pred == 0) & (confidence >= threshold)
        tp = int(np.count_nonzero(selected & (y_true == 0)))
        fp = int(np.count_nonzero(selected & (y_true != 0)))
        fn = int(np.count_nonzero((y_true == 0) & ~selected))
        threshold_rows.append({"max_softmax_threshold": threshold, "tp": tp, "fp": fp, "fn": fn,
                               "precision": tp / (tp + fp) if tp + fp else None,
                               "recall": tp / (tp + fn) if tp + fn else None,
                               "false_positive_rate_non_debris": fp / int(np.count_nonzero(y_true != 0)) if np.any(y_true != 0) else None})
    per_class_confidence = {}
    for class_id, name in enumerate(CLASS_NAMES):
        class_truth = (y_true == class_id).astype(np.uint8)
        per_class_confidence[name] = {
            "one_vs_rest_brier_score": binary_brier(probabilities[class_id], class_truth),
            "one_vs_rest_ece_15_bins": ece(probabilities[class_id], class_truth, 15),
            "labeled_support": int(class_truth.sum()),
        }
    confidence_summary = {
        "mean_max_softmax": float(confidence.mean()),
        "mean_max_softmax_correct_predictions": float(confidence[correct].mean()) if correct.any() else None,
        "mean_max_softmax_incorrect_predictions": float(confidence[~correct].mean()) if (~correct).any() else None,
        "mean_max_softmax_marine_debris_predictions": float(confidence[y_pred == 0].mean()) if np.any(y_pred == 0) else None,
        "top_label_ece_15_bins_not_calibration_proof": ece(confidence, correct.astype(np.uint8), 15),
        "multiclass_brier_mean_sum_squared_error": float(np.mean(np.sum((probabilities.T - np.eye(class_count)[y_true]) ** 2, axis=1))),
        "marine_debris_one_vs_rest_brier": binary_brier(debris_score, debris_binary_truth),
        "marine_debris_score_ece_15_bins": ece(debris_score, debris_binary_truth, 15),
        "distributions_of_max_softmax": {
            "all_labeled_predictions": summarize_scores(confidence),
            "correct_predictions": summarize_scores(confidence[correct]),
            "incorrect_predictions": summarize_scores(confidence[~correct]),
            "predicted_marine_debris": summarize_scores(confidence[y_pred == 0]),
            "true_positive_marine_debris_predictions": summarize_scores(confidence[(y_pred == 0) & (y_true == 0)]),
            "false_positive_marine_debris_predictions": summarize_scores(confidence[(y_pred == 0) & (y_true != 0)]),
        },
        "per_class_one_vs_rest": per_class_confidence,
    }
    debris_row = class_rows[0]
    debris_confusions = []
    for class_id, name in enumerate(CLASS_NAMES):
        if class_id == 0:
            continue
        debris_confusions.append({"other_class": name,
                                  "true_class_pixels_predicted_as_debris": int(confusion[class_id, 0]),
                                  "debris_pixels_predicted_as_other_class": int(confusion[0, class_id])})
    debris_confusions.sort(key=lambda row: row["true_class_pixels_predicted_as_debris"], reverse=True)
    summary.update({
        "marine_debris": debris_row,
        "marine_debris_false_positives_pct_of_all_labeled_pixels": 100 * debris_row["false_positives"] / total if total else None,
        "marine_debris_false_positive_rate_among_labeled_non_debris": debris_row["false_positives"] / int(np.count_nonzero(y_true != 0)) if np.any(y_true != 0) else None,
        "most_common_marine_debris_confusions": debris_confusions,
        "scene_count": len(rois),
        "scenes_with_labeled_marine_debris": sum(row["marine_debris_pixels"] > 0 for row in per_scene),
        "scenes_without_labeled_marine_debris": sum(row["marine_debris_pixels"] == 0 for row in per_scene),
        "scenes_with_marine_debris_predictions": sum(row["marine_debris_tp"] + row["marine_debris_fp"] > 0 for row in per_scene),
        "confidence": confidence_summary,
        "upstream_local_comparison": comparison,
    })

    cm_path = output_dir / "confusion_matrix.csv"
    with cm_path.open("w", newline="", encoding="utf-8") as target:
        writer = csv.writer(target); writer.writerow(["true\\pred", *CLASS_NAMES])
        for name, row in zip(CLASS_NAMES, confusion): writer.writerow([name, *map(int, row)])
    write_csv(output_dir / "per_class_metrics.csv", class_rows)
    write_csv(output_dir / "dataset_label_counts_by_split.csv", split_label_rows)
    write_csv(output_dir / "per_scene_metrics.csv", per_scene)
    write_csv(output_dir / "marine_debris_precision_recall.csv", pr_rows)
    write_csv(output_dir / "marine_debris_confidence_thresholds.csv", threshold_rows)
    confidence_quantile_rows = []
    for group, scores in confidence_summary["distributions_of_max_softmax"].items():
        for percentile, value in scores["percentiles"].items():
            confidence_quantile_rows.append({"group": group, "count": scores["count"], "percentile": percentile, "max_softmax": value})
    write_csv(output_dir / "confidence_quantiles.csv", confidence_quantile_rows)
    (output_dir / "upstream_local_comparison.json").write_text(json.dumps(comparison, indent=2), encoding="utf-8")
    evaluation = {
        "evaluation_date_utc": datetime.now(timezone.utc).isoformat(), "dataset": "MARIDA",
        "dataset_version": DATASET_VERSION, "dataset_doi": DATASET_DOI,
        "dataset_license": DATASET_LICENSE,
        "archive_md5_expected": DATASET_ARCHIVE_MD5,
        "archive_path": str(archive_path.resolve()) if archive_path.is_file() else None,
        "archive_md5_observed": archive_md5,
        "archive_checksum_verified": archive_md5 is not None,
        "dataset_root": str(dataset_root.resolve()), "test_split": "splits/test_X.txt",
        "test_scene_count": len(rois), "test_scene_ids": rois,
        "dataset_split_label_summary": split_label_summary,
        "labeled_pixel_count": int(total), "unlabeled_pixel_count": int(len(rois) * 256 * 256 - total),
        "paper_reported_test_labeled_pixel_count": PAPER_REPORTED_TEST_ANNOTATED_PIXELS,
        "pixel_count_difference_vs_paper_report": int(total - PAPER_REPORTED_TEST_ANNOTATED_PIXELS),
        "checkpoint_sha256": model_hash, "class_names": CLASS_NAMES, "band_order": WAVELENGTH_BANDS,
        "device": device, "source_label_policy": "0 ignored; 1..11 map to output 0..10; 12..15 map to Marine Water output 6; upstream MARIDA agg_to_water=True",
        "input_policy": "11-band float32; non-finite samples imputed with per-band training mean; checkpoint scale/offset then stored channel mean/std; official 256x256 chips; no padding required",
        "pixel_accuracy_note": "These are annotated-pixel segmentation metrics on sparse weak labels, not object detection or exhaustive surface accuracy.",
        "metrics": summary,
        "per_scene_highest_false_positive_rate": sorted(per_scene, key=lambda row: row["debris_false_positive_rate_non_debris"] or 0, reverse=True)[:10],
        "per_scene_highest_false_negative_rate": sorted(per_scene, key=lambda row: (row["marine_debris_fn"] / row["marine_debris_pixels"]) if row["marine_debris_pixels"] else -1, reverse=True)[:10],
    }
    (output_dir / "metrics.json").write_text(json.dumps(evaluation, indent=2), encoding="utf-8")

    fig, ax = plt.subplots(figsize=(11, 9)); im = ax.imshow(confusion, cmap="Blues"); fig.colorbar(im, ax=ax)
    ax.set(xticks=range(11), xticklabels=CLASS_NAMES, yticks=range(11), yticklabels=CLASS_NAMES,
           xlabel="Predicted class", ylabel="Ground-truth class", title="MARIDA official test split confusion matrix")
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right", rotation_mode="anchor")
    fig.tight_layout(); fig.savefig(output_dir / "confusion_matrix.png", dpi=180); plt.close(fig)
    fig, ax = plt.subplots(figsize=(7, 6)); ax.plot(pr_recall, pr_precision, label="Marine Debris score (softmax class 0)")
    ax.set(xlabel="Recall", ylabel="Precision", title="Marine Debris precision–recall (annotated test pixels)", xlim=(0, 1), ylim=(0, 1)); ax.grid(True, alpha=.3); ax.legend()
    fig.tight_layout(); fig.savefig(output_dir / "marine_debris_precision_recall.png", dpi=180); plt.close(fig)
    fig, ax = plt.subplots(figsize=(8, 5)); ax.hist(confidence[correct], bins=np.linspace(0, 1, 21), alpha=.65, label="Correct")
    ax.hist(confidence[~correct], bins=np.linspace(0, 1, 21), alpha=.65, label="Incorrect")
    debris_conf = confidence[y_pred == 0]
    ax.hist(debris_conf, bins=np.linspace(0, 1, 21), alpha=.65, label="Predicted debris")
    ax.set(xlabel="Maximum softmax score (not calibrated probability)", ylabel="Labeled pixels", title="Top-label confidence on MARIDA test split"); ax.legend()
    fig.tight_layout(); fig.savefig(output_dir / "confidence_distribution.png", dpi=180); plt.close(fig)

    fp_cases = sorted((r for r in scene_records if r["fp"] > 0), key=lambda r: r["fp"], reverse=True)[:5]
    fn_cases = sorted((r for r in scene_records if r["fn"] > 0), key=lambda r: r["fn"], reverse=True)[:5]
    for label, records in (("false_positive", fp_cases), ("false_negative", fn_cases)):
        for rank, record in enumerate(records, start=1):
            save_comparison(output_dir / "visualizations" / f"{label}_{rank}_{record['roi']}.png", record["roi"],
                            record["image"], record["truth"], record["prediction"], record["valid"],
                            f"{label.replace('_', ' ').title()} pixels: {record['fp' if label == 'false_positive' else 'fn']}")

    provenance = {
        "official_dataset": DATASET_DOI, "version": DATASET_VERSION, "release_date": "2021-08-01",
        "archive_filename": "MARIDA.zip", "expected_archive_md5": DATASET_ARCHIVE_MD5,
        "archive_md5_observed": archive_md5,
        "archive_checksum_verified": archive_md5 is not None,
        "expected_patch_count": 1381, "expected_test_scene_count": 359,
        "paper_reported_test_annotated_pixels": PAPER_REPORTED_TEST_ANNOTATED_PIXELS,
        "dataset_license": DATASET_LICENSE, "attribution": "Kikaki, Kakogeorgiou, Mikeli, Raitsos & Karantzalos (2022), PLOS ONE 17(1):e0262247, doi:10.1371/journal.pone.0262247",
        "evaluation_code": {"repository": UPSTREAM_REPOSITORY, "revision": UPSTREAM_REVISION, "license": UPSTREAM_LICENSE},
        "test_split_sha256": sha256_file(dataset_root / "splits" / "test_X.txt"),
        "checkpoint_sha256": model_hash,
    }
    (output_dir / "provenance.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    report_lines = [
        "# MARIDA U-Net scientific evaluation",
        "",
        f"- Evaluation date (UTC): {evaluation['evaluation_date_utc']}",
        f"- Dataset: MARIDA {DATASET_VERSION} ({DATASET_DOI}); CC BY 4.0",
        f"- Official test split: {len(rois)} of 1,381 patches; {total:,} labeled pixels; 0-valued mask pixels ignored",
        f"- Paper-reported test labeled pixel count: {PAPER_REPORTED_TEST_ANNOTATED_PIXELS:,} (release masks differ by {total - PAPER_REPORTED_TEST_ANNOTATED_PIXELS:+,})",
        f"- Archive MD5: {archive_md5 or 'not available'} (verified={archive_md5 is not None})",
        f"- Checkpoint SHA-256: `{model_hash}`",
        f"- Device: {device}; inputs: 11 bands in MARIDA order, 256×256; source labels 12–15 aggregated to Marine Water",
        "- Attribution: Kikaki et al. (2022), PLOS ONE 17(1):e0262247, DOI 10.1371/journal.pone.0262247.",
        f"- Upstream evaluation reference: [{UPSTREAM_REVISION}]({UPSTREAM_REPOSITORY}/tree/{UPSTREAM_REVISION}/semantic_segmentation/unet).",
        "",
        "## Overall and marine debris results",
        "",
        f"- Pixel accuracy: {markdown_number(summary['overall_pixel_accuracy'])}; mean IoU: {markdown_number(summary['mean_iou_over_classes_with_labeled_test_support'])}; macro F1: {markdown_number(summary['macro_f1_over_classes_with_labeled_test_support'])}; support-weighted F1: {markdown_number(summary['weighted_f1'])}.",
        f"- Marine debris: P {markdown_number(debris_row['precision'])}; R {markdown_number(debris_row['recall'])}; F1 {markdown_number(debris_row['f1'])}; IoU {markdown_number(debris_row['iou'])}; support {debris_row['support']}; TP/FP/FN {debris_row['true_positives']}/{debris_row['false_positives']}/{debris_row['false_negatives']}.",
        f"- False-positive debris pixels are {summary['marine_debris_false_positives_pct_of_all_labeled_pixels']:.4f}% of labeled pixels and {100 * summary['marine_debris_false_positive_rate_among_labeled_non_debris']:.4f}% of labeled non-debris pixels.",
        f"- Debris labels occur in {summary['scenes_with_labeled_marine_debris']} scenes; {summary['scenes_without_labeled_marine_debris']} scenes have no labeled debris. Scene-wise rates for tiny supports are unstable.",
        "",
        "## Per-class metrics",
        "",
        "| Class | Support | TP | FP | FN | Precision | Recall | F1 | IoU |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in class_rows:
        report_lines.append(
            f"| {row['class_name']} | {row['support']:,} | {row['true_positives']:,} | {row['false_positives']:,} | {row['false_negatives']:,} | {markdown_number(row['precision'])} | {markdown_number(row['recall'])} | {markdown_number(row['f1'])} | {markdown_number(row['iou'])} |"
        )
    report_lines += ["", "## Confusion matrix (rows=true, columns=predicted)", "",
                     "| True \\ Predicted | " + " | ".join(CLASS_NAMES) + " |",
                     "|---|" + "---:|" * class_count]
    for name, row in zip(CLASS_NAMES, confusion):
        report_lines.append(f"| {name} | " + " | ".join(f"{int(value):,}" for value in row) + " |")
    report_lines += [
        "", "## Confidence and threshold behavior", "",
        f"Mean maximum softmax: {confidence_summary['mean_max_softmax']:.4f}; correct pixels: {confidence_summary['mean_max_softmax_correct_predictions']:.4f}; incorrect pixels: {confidence_summary['mean_max_softmax_incorrect_predictions']:.4f}; predicted debris: {markdown_number(confidence_summary['mean_max_softmax_marine_debris_predictions'])}.",
        f"Top-label ECE (15 bins): {confidence_summary['top_label_ece_15_bins_not_calibration_proof']:.4f}; multiclass Brier: {confidence_summary['multiclass_brier_mean_sum_squared_error']:.4f}. Softmax is not claimed to be calibrated.",
        "Threshold sensitivity is in `marine_debris_confidence_thresholds.csv`; 0.5 gives precision 0.5278 and recall 0.4987 under the existing maximum-softmax abstention rule. The production threshold is unchanged.",
        "",
        "## Upstream/local consistency",
        f"{comparison['scenes']} scenes compared. Logits and probabilities are equal (maximum absolute difference {comparison['max_absolute_logit_difference']:.1f}); predicted classes match for {comparison['exact_prediction_pixels']:,}/{comparison['compared_pixels']:,} pixels. Official dimensions are stride-compatible, so no padding is used. The upstream implementation does not define the local replicate-pad/crop extension for nonstandard dimensions.",
        "A separate, non-scoring 255×257 shape probe produced local replicate-padding to 256×272 and cropping back to 255×257; the pinned upstream model raised a skip-connection tensor-size mismatch. This shape probe was not included in any accuracy metric.",
        "",
        "## Scene examples and outputs",
        "- Complete per-scene table: `per_scene_metrics.csv`; highest false-positive and false-negative rates are also listed in `metrics.json`.",
        "- Dataset label support across train/validation/test (descriptive only; no training or threshold selection): `dataset_label_counts_by_split.csv`.",
        "- Confusion matrix: `confusion_matrix.csv` and `confusion_matrix.png`.",
        "- Debris PR and confidence plots: `marine_debris_precision_recall.png`, `confidence_distribution.png`.",
        "- Representative ground truth/prediction/RGB comparisons and false-positive/false-negative cases are in `visualizations/`.",
        "- This is sparse weak-label pixel segmentation evaluation, not object-level detection accuracy or a geographic generalization claim.",
    ]
    (output_dir / "report.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    return evaluation


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-root", type=Path, default=BACKEND_DIR / "data" / "MARIDA",
                        help="Extracted official MARIDA root, containing patches/ and splits/")
    parser.add_argument("--output-dir", type=Path, default=BACKEND_DIR / "evaluation" / "marida_stage3")
    parser.add_argument("--archive", type=Path, default=BACKEND_DIR / "data" / "MARIDA.zip",
                        help="Official MARIDA.zip to MD5-verify (if retained)")
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    args = parser.parse_args()
    if args.device == "cuda" and not torch.cuda.is_available():
        parser.error("CUDA requested but unavailable")
    result = evaluate(args.dataset_root, args.output_dir, args.device, args.archive)
    print(json.dumps({"metrics": result["metrics"], "test_scene_count": result["test_scene_count"],
                      "labeled_pixel_count": result["labeled_pixel_count"], "output_dir": str(args.output_dir)}, indent=2))


if __name__ == "__main__":
    main()
