"""Validation-only threshold, calibration, uncertainty, and label-review analysis.

This script reads MARIDA's train IDs (for split-disjointness verification) and
validation images/masks only. It never reads test_X.txt or test imagery, never
calls a production route, never writes to official data, and never changes the
checkpoint or production inference settings.
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
from scipy.optimize import minimize_scalar
from scipy.special import logsumexp, softmax
from sklearn.metrics import precision_recall_curve

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.ml.satellite.detector import DebrisDetector  # noqa: E402
from evaluate_marida import (  # noqa: E402
    CLASS_NAMES,
    DATASET_ARCHIVE_MD5,
    DATASET_DOI,
    DATASET_LICENSE,
    DATASET_VERSION,
    EXPECTED_MODEL_SHA256,
    METADATA_PATH,
    MODEL_PATH,
    UPSTREAM_REVISION,
    UPSTREAM_REPOSITORY,
    WAVELENGTH_BANDS,
    ece,
    map_labels,
    md5_file,
    normalize,
    prepare_local_input,
    roi_paths,
    sha256_file,
)

THRESHOLDS = [0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45,
              0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.90]
CONFUSION_TARGETS = ["Marine Water", "Ship", "Clouds", "Natural Organic Material", "Foam", "Sparse Sargassum"]
DEBRIS_ID = 0
RGB_BANDS = (3, 2, 1)
PERCENTILES = (0, 5, 25, 50, 75, 95, 100)


def read_roi_ids(dataset_root: Path) -> tuple[list[str], set[str]]:
    """Read train/validation manifests only; leave test manifest untouched."""
    train_path = dataset_root / "splits" / "train_X.txt"
    val_path = dataset_root / "splits" / "val_X.txt"
    if not train_path.is_file() or not val_path.is_file():
        raise FileNotFoundError("Official MARIDA train_X.txt and val_X.txt are required")
    train_ids = [x.strip() for x in train_path.read_text(encoding="utf-8-sig").splitlines() if x.strip()]
    val_ids = [x.strip() for x in val_path.read_text(encoding="utf-8-sig").splitlines() if x.strip()]
    if len(train_ids) != 694 or len(set(train_ids)) != 694:
        raise ValueError("Expected 694 unique official training patch IDs")
    if len(val_ids) != 328 or len(set(val_ids)) != 328:
        raise ValueError("Expected 328 unique official validation patch IDs")
    overlap = set(train_ids).intersection(val_ids)
    if overlap:
        raise ValueError(f"Train and validation IDs overlap: {sorted(overlap)[:5]}")
    for roi in val_ids:
        image_path, mask_path = roi_paths(dataset_root, roi)
        if not image_path.is_file() or not mask_path.is_file():
            raise FileNotFoundError(f"Validation patch {roi} lacks image or class mask")
    return sorted(val_ids), set(train_ids)


def resolve_validation_dataset_root(path: Path) -> Path:
    """Resolve an extracted MARIDA root without probing the test split path."""
    for candidate in (path, path / "MARIDA", path / "data"):
        if ((candidate / "patches").is_dir()
                and (candidate / "splits" / "train_X.txt").is_file()
                and (candidate / "splits" / "val_X.txt").is_file()):
            return candidate
    raise FileNotFoundError(f"Expected patches/, train_X.txt, and val_X.txt beneath {path}")


def load_validation_patch(dataset_root: Path, roi: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    image_path, mask_path = roi_paths(dataset_root, roi)
    with rasterio.open(image_path) as dataset:
        raw = dataset.read().astype(np.float32, copy=False)
        masks = dataset.read_masks() == 0
        if dataset.count != 11 or raw.shape != (11, 256, 256):
            raise ValueError(f"Unexpected MARIDA image shape for {roi}: {raw.shape}")
    invalid_channels = masks | ~np.isfinite(raw)
    invalid_pixel = invalid_channels.any(axis=0)
    prepared = np.array(raw, dtype=np.float32, copy=True)
    prepared[invalid_channels] = np.nan
    with rasterio.open(mask_path) as dataset:
        source_labels = dataset.read(1).astype(np.int16, copy=False)
    if source_labels.shape != (256, 256) or np.any((source_labels < 0) | (source_labels > 15)):
        raise ValueError(f"Unexpected MARIDA label mask for {roi}")
    labels, labeled = map_labels(source_labels)
    return prepared, labels, invalid_pixel


def confusion_counts(y_true: np.ndarray, y_pred: np.ndarray) -> np.ndarray:
    return np.bincount(y_true.astype(np.int64) * 11 + y_pred.astype(np.int64), minlength=121).reshape(11, 11)


def binary_metrics(y_true_debris: np.ndarray, predicted_debris: np.ndarray) -> dict[str, Any]:
    tp = int(np.count_nonzero(y_true_debris & predicted_debris))
    fp = int(np.count_nonzero(~y_true_debris & predicted_debris))
    fn = int(np.count_nonzero(y_true_debris & ~predicted_debris))
    support = int(y_true_debris.sum())
    predicted = int(predicted_debris.sum())
    precision = tp / predicted if predicted else None
    recall = tp / support if support else None
    f1 = 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None
    iou = tp / (tp + fp + fn) if tp + fp + fn else None
    return {"support": support, "predicted_debris_pixels_labeled": predicted,
            "true_positives": tp, "false_positives": fp, "false_negatives": fn,
            "precision": precision, "recall": recall, "f1": f1, "iou": iou}


def threshold_predictions(argmax: np.ndarray, max_confidence: np.ndarray,
                          debris_probability: np.ndarray, threshold: float) -> tuple[np.ndarray, np.ndarray]:
    """Return distinct argmax-abstention and debris one-vs-rest decisions."""
    strategy_a = (argmax == DEBRIS_ID) & (max_confidence >= threshold)
    strategy_b = debris_probability >= threshold
    return strategy_a, strategy_b


def metric_row(strategy: str, threshold: float, truth: np.ndarray, debris_prediction: np.ndarray,
               excluded: np.ndarray, valid_pixel_prediction_count: int,
               unlabeled_valid_debris_count: int, invalid_debris_count: int,
               override_count: int = 0) -> dict[str, Any]:
    result = binary_metrics(truth == DEBRIS_ID, debris_prediction)
    total_labeled = int(truth.size)
    result.update({
        "strategy": strategy,
        "threshold": threshold,
        "labeled_pixel_count": total_labeled,
        "labeled_pixels_excluded_by_threshold": int(excluded.sum()),
        "labeled_pixels_excluded_pct": 100 * float(excluded.mean()) if total_labeled else None,
        "predicted_debris_pixels_valid_imagery_all": valid_pixel_prediction_count,
        "predicted_debris_pixels_unlabeled_valid_imagery": unlabeled_valid_debris_count,
        "predicted_debris_pixels_invalid_imagery": invalid_debris_count,
        "class_probability_override_of_argmax_pixels_labeled": override_count,
    })
    return result


def score_summary(values: np.ndarray) -> dict[str, Any]:
    if values.size == 0:
        return {"count": 0, "mean": None, "std": None, "percentiles": {}}
    q = np.percentile(values, PERCENTILES)
    return {"count": int(values.size), "mean": float(values.mean()), "std": float(values.std()),
            "percentiles": {str(p): float(v) for p, v in zip(PERCENTILES, q)}}


def multiclass_brier(probabilities: np.ndarray, truth: np.ndarray) -> float:
    one_hot = np.eye(11, dtype=np.float64)[truth]
    return float(np.mean(np.sum((probabilities.astype(np.float64) - one_hot) ** 2, axis=1)))


def calibration_summary(probabilities: np.ndarray, truth: np.ndarray) -> dict[str, Any]:
    predicted = probabilities.argmax(axis=1)
    top_conf = probabilities.max(axis=1)
    correct = predicted == truth
    return {
        "labeled_pixel_count": int(truth.size),
        "negative_log_likelihood": float(-np.log(np.maximum(probabilities[np.arange(truth.size), truth], 1e-15)).mean()),
        "multiclass_brier_score_sum_over_classes": multiclass_brier(probabilities, truth),
        "top_label_ece_15_equal_width_bins": ece(top_conf, correct.astype(np.uint8), 15),
        "marine_debris_one_vs_rest_brier": float(np.mean((probabilities[:, 0] - (truth == 0)) ** 2)),
        "marine_debris_one_vs_rest_ece_15_equal_width_bins": ece(probabilities[:, 0], (truth == 0).astype(np.uint8), 15),
        "top_label_accuracy": float(correct.mean()),
        "mean_top_label_confidence": float(top_conf.mean()),
    }


def reliability_bins(scores: np.ndarray, outcomes: np.ndarray, bins: int = 15) -> list[dict[str, Any]]:
    edges = np.linspace(0, 1, bins + 1)
    rows = []
    for low, high in zip(edges[:-1], edges[1:]):
        selected = (scores >= low) & ((scores < high) if high < 1 else (scores <= high))
        rows.append({"lower": float(low), "upper": float(high), "count": int(selected.sum()),
                     "mean_score": float(scores[selected].mean()) if selected.any() else None,
                     "observed_frequency": float(outcomes[selected].mean()) if selected.any() else None})
    return rows


def reliability_error(rows: list[dict[str, Any]], total: int) -> float | None:
    if not total:
        return None
    return float(sum(r["count"] / total * abs(r["mean_score"] - r["observed_frequency"])
                     for r in rows if r["count"]))


def fit_temperature(logits: np.ndarray, truth: np.ndarray) -> dict[str, Any]:
    """Fit one scalar log-temperature on validation labeled pixels only."""
    x = logits.astype(np.float64, copy=False)
    rows = np.arange(truth.size)

    def objective(log_temperature: float) -> float:
        scaled = x / np.exp(log_temperature)
        return float(np.mean(logsumexp(scaled, axis=1) - scaled[rows, truth]))

    result = minimize_scalar(objective, bounds=(-3.0, 3.0), method="bounded", options={"xatol": 1e-5})
    temperature = float(np.exp(result.x))
    return {"temperature": temperature, "fit_method": "bounded scalar minimization of validation multiclass NLL",
            "optimization_bounds_log_temperature": [-3.0, 3.0], "validation_labeled_pixel_count": int(truth.size),
            "optimizer_success": bool(result.success), "validation_nll_at_fit": float(result.fun)}


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8") as target:
        writer = csv.DictWriter(target, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def rgb_preview(image: np.ndarray) -> np.ndarray:
    rgb = np.moveaxis(image[list(RGB_BANDS)], 0, -1).astype(np.float32)
    values = rgb[np.isfinite(rgb)]
    if not values.size:
        return np.zeros((*rgb.shape[:2], 3), dtype=np.float32)
    low, high = np.percentile(values, [2, 98])
    if high <= low:
        high = low + 1
    return np.clip(np.nan_to_num((rgb - low) / (high - low), nan=0, posinf=1, neginf=0), 0, 1)


def analyze_scene(dataset_root: Path, roi: str, detector: DebrisDetector) -> dict[str, Any]:
    image, labels, invalid = load_validation_patch(dataset_root, roi)
    local, shape = prepare_local_input(image, detector)
    with torch.inference_mode():
        logits_t = detector.model(local)[..., :shape[0], :shape[1]]
        probs_t = torch.softmax(logits_t, dim=1)
        max_conf_t, pred_t = probs_t.max(dim=1)
    logits = logits_t[0].cpu().numpy()
    probs = probs_t[0].cpu().numpy()
    pred = pred_t[0].cpu().numpy().astype(np.int16)
    max_conf = max_conf_t[0].cpu().numpy()
    entropy = -(probs * np.log(np.maximum(probs, 1e-12))).sum(axis=0) / np.log(11.0)
    labeled = labels >= 0
    image_valid = ~invalid
    return {"roi": roi, "image": image, "labels": labels, "invalid": invalid, "labeled": labeled,
            "image_valid": image_valid, "logits": logits, "probabilities": probs, "prediction": pred,
            "max_confidence": max_conf, "debris_probability": probs[0], "normalized_entropy": entropy}


def save_gallery(path: Path, record: dict[str, Any]) -> None:
    from matplotlib.colors import BoundaryNorm, ListedColormap

    image = record["image"]
    labels = record["labels"]
    pred = record["prediction"]
    valid = record["image_valid"]
    cmap = plt.get_cmap("tab20", 11).copy()
    cmap.set_bad("black")
    bounds = np.arange(-0.5, 11.5, 1)
    norm = BoundaryNorm(bounds, cmap.N)
    truth_view = np.ma.masked_where(~record["labeled"], labels)
    pred_view = np.ma.masked_where(~valid, pred)
    debris_probability = np.ma.masked_where(~valid, record["debris_probability"])
    uncertainty = np.ma.masked_where(~valid, record["normalized_entropy"])
    label_state = np.full(labels.shape, 1, dtype=np.uint8)  # unlabeled, valid imagery
    label_state[record["labeled"]] = 0
    label_state[record["invalid"]] = 2
    label_cmap = ListedColormap(["#32a852", "#a9b4bd", "#d62728"])

    fig, axes = plt.subplots(2, 3, figsize=(16, 9), constrained_layout=True)
    axes = axes.ravel()
    axes[0].imshow(rgb_preview(image)); axes[0].set_title("Sentinel-2 RGB (B4/B3/B2; 2–98% stretch)")
    axes[1].imshow(truth_view, cmap=cmap, norm=norm, interpolation="nearest"); axes[1].set_title("Ground truth (unlabeled black)")
    axes[2].imshow(pred_view, cmap=cmap, norm=norm, interpolation="nearest"); axes[2].set_title("Model prediction")
    axes[3].imshow(debris_probability, cmap="magma", vmin=0, vmax=1); axes[3].set_title("Marine Debris softmax score")
    fig.colorbar(axes[3].images[0], ax=axes[3], fraction=.046, pad=.04)
    axes[4].imshow(uncertainty, cmap="viridis", vmin=0, vmax=1); axes[4].set_title("Normalized predictive entropy")
    fig.colorbar(axes[4].images[0], ax=axes[4], fraction=.046, pad=.04)
    axes[5].imshow(label_state, cmap=label_cmap, vmin=0, vmax=2, interpolation="nearest")
    axes[5].set_title("Label coverage: green labeled, gray unlabeled, red invalid image")
    for axis in axes:
        axis.axis("off")
    fig.suptitle(f"Validation patch {record['roi']} — unlabeled pixels are not false positives")
    fig.savefig(path, dpi=150)
    plt.close(fig)


def evaluate(dataset_root: Path, output_dir: Path, archive: Path | None = None) -> dict[str, Any]:
    dataset_root = resolve_validation_dataset_root(dataset_root)
    archive = archive or BACKEND_DIR / "data" / "MARIDA.zip"
    archive_md5 = md5_file(archive) if archive.is_file() else None
    if archive_md5 is not None and archive_md5.lower() != DATASET_ARCHIVE_MD5:
        raise ValueError(f"Dataset archive MD5 mismatch: {archive_md5}")
    model_sha = sha256_file(MODEL_PATH)
    if model_sha != EXPECTED_MODEL_SHA256:
        raise ValueError(f"Unexpected checkpoint SHA-256: {model_sha}")
    metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    if metadata["class_names"] != CLASS_NAMES or metadata["band_order"] != WAVELENGTH_BANDS:
        raise ValueError("Checkpoint class or band metadata differs from expected MARIDA taxonomy")
    val_rois, train_ids = read_roi_ids(dataset_root)
    if set(val_rois).intersection(train_ids):
        raise AssertionError("Train/validation split leakage")
    output_dir.mkdir(parents=True, exist_ok=True)
    gallery_dir = output_dir / "visualizations"
    gallery_dir.mkdir(exist_ok=True)

    detector = DebrisDetector(MODEL_PATH, device="cpu", class_names=CLASS_NAMES, band_order=WAVELENGTH_BANDS)
    thresholds_by_scene: list[dict[str, Any]] = []
    scene_rows: list[dict[str, Any]] = []
    confusion = np.zeros((11, 11), dtype=np.int64)
    labeled_logits: list[np.ndarray] = []
    labeled_true: list[np.ndarray] = []
    labeled_pred: list[np.ndarray] = []
    labeled_maxconf: list[np.ndarray] = []
    labeled_p_debris: list[np.ndarray] = []
    labeled_entropy: list[np.ndarray] = []
    labeled_imagery_valid: list[np.ndarray] = []
    labeled_margin: list[np.ndarray] = []
    unlabeled_valid_scores: dict[str, list[np.ndarray]] = {"max_confidence": [], "debris_probability": [], "entropy": []}
    invalid_scores: dict[str, list[np.ndarray]] = {"max_confidence": [], "debris_probability": [], "entropy": []}
    spectral_sum = np.zeros((11, 11), dtype=np.float64)
    spectral_sum_sq = np.zeros((11, 11), dtype=np.float64)
    spectral_count = np.zeros(11, dtype=np.int64)
    confusion_pair_probs: dict[str, list[np.ndarray]] = {name: [] for name in CONFUSION_TARGETS}
    valid_pixel_debris_by_threshold = {t: 0 for t in THRESHOLDS}
    unlabeled_valid_debris_by_threshold = {t: 0 for t in THRESHOLDS}
    invalid_debris_by_threshold = {t: 0 for t in THRESHOLDS}
    invalid_counts = {"invalid_pixels": 0, "valid_image_pixels": 0, "invalid_labeled_pixels": 0,
                      "valid_labeled_pixels": 0, "unlabeled_valid_image_pixels": 0,
                      "invalid_unlabeled_pixels": 0, "predicted_debris_invalid": 0,
                      "predicted_debris_unlabeled_valid": 0}
    class_names_to_id = {name: i for i, name in enumerate(CLASS_NAMES)}
    torch.set_num_threads(max(1, min(4, torch.get_num_threads())))

    for index, roi in enumerate(val_rois, start=1):
        rec = analyze_scene(dataset_root, roi, detector)
        image, labels, invalid = rec["image"], rec["labels"], rec["invalid"]
        labeled, image_valid = rec["labeled"], rec["image_valid"]
        pred, probs, conf = rec["prediction"], rec["probabilities"], rec["max_confidence"]
        p_debris, entropy = rec["debris_probability"], rec["normalized_entropy"]
        y = labels[labeled].astype(np.int16)
        yp = pred[labeled].astype(np.int16)
        if y.size:
            confusion += confusion_counts(y, yp)
            labeled_logits.append(rec["logits"].reshape(11, -1)[:, labeled.ravel()].T.astype(np.float32))
            labeled_true.append(y)
            labeled_pred.append(yp)
            labeled_maxconf.append(conf[labeled].astype(np.float32))
            labeled_p_debris.append(p_debris[labeled].astype(np.float32))
            labeled_entropy.append(entropy[labeled].astype(np.float32))
            labeled_imagery_valid.append(image_valid[labeled])
            competitor = np.max(np.delete(probs, DEBRIS_ID, axis=0), axis=0)
            labeled_margin.append((p_debris - competitor)[labeled].astype(np.float32))
            image_values = image.transpose(1, 2, 0)[labeled & image_valid]
            label_values = labels[labeled & image_valid]
            finite_rows = np.isfinite(image_values).all(axis=1)
            image_values = image_values[finite_rows]
            label_values = label_values[finite_rows]
            for cls in range(11):
                values = image_values[label_values == cls]
                if values.size:
                    spectral_count[cls] += values.shape[0]
                    spectral_sum[cls] += values.sum(axis=0)
                    spectral_sum_sq[cls] += np.square(values, dtype=np.float64).sum(axis=0)
            for class_name in CONFUSION_TARGETS:
                cls = class_names_to_id[class_name]
                class_pixels = labeled & image_valid & (labels == cls)
                if class_pixels.any():
                    confusion_pair_probs[class_name].append(probs[DEBRIS_ID][class_pixels].astype(np.float32))

        valid_count = int(image_valid.sum())
        invalid_count = int(invalid.sum())
        unlabeled_valid = image_valid & ~labeled
        invalid_counts["invalid_pixels"] += invalid_count
        invalid_counts["valid_image_pixels"] += valid_count
        invalid_counts["invalid_labeled_pixels"] += int((invalid & labeled).sum())
        invalid_counts["valid_labeled_pixels"] += int((image_valid & labeled).sum())
        invalid_counts["unlabeled_valid_image_pixels"] += int(unlabeled_valid.sum())
        invalid_counts["invalid_unlabeled_pixels"] += int((invalid & ~labeled).sum())
        invalid_counts["predicted_debris_invalid"] += int(((pred == 0) & invalid).sum())
        invalid_counts["predicted_debris_unlabeled_valid"] += int(((pred == 0) & unlabeled_valid).sum())
        for key, values in (("max_confidence", conf), ("debris_probability", p_debris), ("entropy", entropy)):
            if unlabeled_valid.any():
                unlabeled_valid_scores[key].append(values[unlabeled_valid].astype(np.float32))
            if invalid.any():
                invalid_scores[key].append(values[invalid].astype(np.float32))

        cm_scene = confusion_counts(y, yp) if y.size else np.zeros((11, 11), dtype=np.int64)
        support_debris = int((y == 0).sum())
        pred_debris_labeled = yp == 0
        gt_debris = y == 0
        tp = int(np.count_nonzero(gt_debris & pred_debris_labeled))
        fp = int(np.count_nonzero(~gt_debris & pred_debris_labeled))
        fn = int(np.count_nonzero(gt_debris & ~pred_debris_labeled))
        nondebris_support = int((y != 0).sum())
        scene = {
            "roi": roi,
            "labeled_pixels": int(y.size),
            "labeled_pixels_valid_imagery": int((labeled & image_valid).sum()),
            "labeled_pixels_invalid_imagery": int((labeled & invalid).sum()),
            "unlabeled_pixels_valid_imagery": int(unlabeled_valid.sum()),
            "unlabeled_pixels_invalid_imagery": int((~labeled & invalid).sum()),
            "marine_debris_ground_truth_pixels": support_debris,
            "marine_debris_true_positives_labeled": tp,
            "marine_debris_false_positives_labeled": fp,
            "marine_debris_false_negatives_labeled": fn,
            "marine_debris_precision_labeled": tp / (tp + fp) if tp + fp else None,
            "marine_debris_recall_labeled": tp / support_debris if support_debris else None,
            "marine_debris_iou_labeled": tp / (tp + fp + fn) if tp + fp + fn else None,
            "marine_water_to_debris_labeled": int(cm_scene[6, 0]),
            "ship_to_debris_labeled": int(cm_scene[4, 0]),
            "foam_to_debris_labeled": int(cm_scene[8, 0]),
            "cloud_to_debris_labeled": int(cm_scene[5, 0]),
            "natural_material_to_debris_labeled": int(cm_scene[3, 0]),
            "sparse_sargassum_to_debris_labeled": int(cm_scene[2, 0]),
            "marine_debris_to_water_labeled": int(cm_scene[0, 6]),
            "marine_debris_predictions_unlabeled_valid": int(((pred == 0) & unlabeled_valid).sum()),
            "marine_debris_predictions_invalid_imagery": int(((pred == 0) & invalid).sum()),
            "marine_debris_prediction_rate_valid_imagery": float(((pred == 0) & image_valid).sum() / valid_count) if valid_count else None,
            "mean_debris_probability_labeled": float(p_debris[labeled].mean()) if labeled.any() else None,
            "mean_debris_probability_unlabeled_valid": float(p_debris[unlabeled_valid].mean()) if unlabeled_valid.any() else None,
            "mean_normalized_entropy_labeled": float(entropy[labeled].mean()) if labeled.any() else None,
            "mean_normalized_entropy_unlabeled_valid": float(entropy[unlabeled_valid].mean()) if unlabeled_valid.any() else None,
            "labeled_disagreement_rate": float(np.mean(yp != y)) if y.size else None,
        }
        scene_rows.append(scene)
        # Threshold prediction counts over the entire image are kept distinct
        # from scored labeled pixels. Unlabeled pixels are never scored as FP.
        for threshold in THRESHOLDS:
            selected_a = (pred == 0) & (conf >= threshold)
            selected_b = p_debris >= threshold
            valid_pixel_debris_by_threshold[threshold] += int((selected_a & image_valid).sum())
            unlabeled_valid_debris_by_threshold[threshold] += int((selected_a & unlabeled_valid).sum())
            invalid_debris_by_threshold[threshold] += int((selected_a & invalid).sum())
            # Strategy B counts too, stored on a separate set of keys below.
            valid_pixel_debris_by_threshold[("class_probability", threshold)] = valid_pixel_debris_by_threshold.get(("class_probability", threshold), 0) + int((selected_b & image_valid).sum())
            unlabeled_valid_debris_by_threshold[("class_probability", threshold)] = unlabeled_valid_debris_by_threshold.get(("class_probability", threshold), 0) + int((selected_b & unlabeled_valid).sum())
            invalid_debris_by_threshold[("class_probability", threshold)] = invalid_debris_by_threshold.get(("class_probability", threshold), 0) + int((selected_b & invalid).sum())

        if index % 25 == 0 or index == len(val_rois):
            print(f"Analyzed {index}/{len(val_rois)} official validation patches", flush=True)

    y_true = np.concatenate(labeled_true)
    y_pred = np.concatenate(labeled_pred)
    logits = np.concatenate(labeled_logits).astype(np.float64)
    max_conf = np.concatenate(labeled_maxconf)
    p_debris = np.concatenate(labeled_p_debris)
    entropy_labeled = np.concatenate(labeled_entropy)
    imagery_valid_labeled = np.concatenate(labeled_imagery_valid)
    margin_debris = np.concatenate(labeled_margin)
    probs_raw = softmax(logits, axis=1)
    calibration_before = calibration_summary(probs_raw, y_true)
    temp_fit = fit_temperature(logits, y_true)
    temperature = temp_fit["temperature"]
    probs_calibrated = softmax(logits / temperature, axis=1)
    calibration_after = calibration_summary(probs_calibrated, y_true)

    threshold_rows: list[dict[str, Any]] = []
    true_debris = y_true == 0
    for threshold in THRESHOLDS:
        # A. Keep the existing argmax class only if top-label confidence passes.
        selected_a, _ = threshold_predictions(y_pred, max_conf, p_debris, threshold)
        excluded_a = max_conf < threshold
        row_a = metric_row(
            "max_softmax_argmax_debris", threshold, y_true, selected_a, excluded_a,
            valid_pixel_debris_by_threshold[threshold],
            unlabeled_valid_debris_by_threshold[threshold], invalid_debris_by_threshold[threshold],
        )
        row_a["labeled_pixels_excluded_pct_valid_imagery_only"] = (
            100 * float((excluded_a & imagery_valid_labeled).mean()) if y_true.size else None
        )
        threshold_rows.append(row_a)

        # B. Binary class-specific decision: P(debris) >= t, even when another
        # class has the largest score. This is intentionally distinct from A.
        _, selected_b = threshold_predictions(y_pred, max_conf, p_debris, threshold)
        row_b = metric_row(
            "marine_debris_probability_one_vs_rest", threshold, y_true, selected_b,
            np.zeros(y_true.shape, dtype=bool),
            valid_pixel_debris_by_threshold[("class_probability", threshold)],
            unlabeled_valid_debris_by_threshold[("class_probability", threshold)],
            invalid_debris_by_threshold[("class_probability", threshold)],
            int(np.count_nonzero(selected_b & (y_pred != 0))),
        )
        row_b["labeled_pixels_below_debris_probability_threshold"] = int((p_debris < threshold).sum())
        row_b["labeled_pixels_below_debris_probability_threshold_pct"] = 100 * float((p_debris < threshold).mean())
        row_b["labeled_pixels_excluded_pct_valid_imagery_only"] = 0.0
        threshold_rows.append(row_b)

    # Threshold selection is validation-only and is reported as an experimental
    # candidate, not a production setting. Ties prefer the lower threshold.
    best_validation_thresholds = {}
    for strategy in ("max_softmax_argmax_debris", "marine_debris_probability_one_vs_rest"):
        strategy_rows = [r for r in threshold_rows if r["strategy"] == strategy]
        best = max(strategy_rows, key=lambda r: ((r["f1"] or -1), -r["threshold"]))
        best_validation_thresholds[strategy] = {"threshold": best["threshold"], "precision": best["precision"],
                                                "recall": best["recall"], "f1": best["f1"],
                                                "iou": best["iou"], "validation_only_candidate": True}

    # Validation-only labeled reliability arrays.
    raw_top = probs_raw.max(axis=1)
    raw_correct = probs_raw.argmax(axis=1) == y_true
    cal_top = probs_calibrated.max(axis=1)
    cal_correct = probs_calibrated.argmax(axis=1) == y_true
    reliability = {
        "raw_top_label": reliability_bins(raw_top, raw_correct.astype(np.uint8)),
        "temperature_scaled_top_label": reliability_bins(cal_top, cal_correct.astype(np.uint8)),
        "raw_marine_debris_ovr": reliability_bins(probs_raw[:, 0], true_debris.astype(np.uint8)),
        "temperature_scaled_marine_debris_ovr": reliability_bins(probs_calibrated[:, 0], true_debris.astype(np.uint8)),
    }
    calibration_before["marine_debris_ece_15_bins"] = reliability_error(reliability["raw_marine_debris_ovr"], y_true.size)
    calibration_after["marine_debris_ece_15_bins"] = reliability_error(reliability["temperature_scaled_marine_debris_ovr"], y_true.size)

    # Confidence distributions on annotated pixels, by correctness, class, and debris outcome.
    uncertainty_rows: list[dict[str, Any]] = []
    labeled_argmax = probs_raw.argmax(axis=1)
    groups: dict[str, np.ndarray] = {
        "all_labeled": np.ones(y_true.shape, dtype=bool),
        "correct_labeled": labeled_argmax == y_true,
        "incorrect_labeled": labeled_argmax != y_true,
        "true_marine_debris": y_true == 0,
        "predicted_marine_debris_labeled": labeled_argmax == 0,
        "true_positive_marine_debris": (y_true == 0) & (labeled_argmax == 0),
        "false_positive_marine_debris_labeled": (y_true != 0) & (labeled_argmax == 0),
        "false_negative_marine_debris_labeled": (y_true == 0) & (labeled_argmax != 0),
        "invalid_imagery_labeled": ~imagery_valid_labeled,
        "valid_imagery_labeled": imagery_valid_labeled,
    }
    for class_id, name in enumerate(CLASS_NAMES):
        groups[f"ground_truth_class_{class_id}_{name.replace(' ', '_')}"] = y_true == class_id
    for group_name, mask in groups.items():
        uncertainty_rows.append({"group": group_name, "count": int(mask.sum()),
                                 "mean_max_softmax": float(raw_top[mask].mean()) if mask.any() else None,
                                 "median_max_softmax": float(np.median(raw_top[mask])) if mask.any() else None,
                                 "p05_max_softmax": float(np.percentile(raw_top[mask], 5)) if mask.any() else None,
                                 "p95_max_softmax": float(np.percentile(raw_top[mask], 95)) if mask.any() else None,
                                 "mean_marine_debris_probability": float(probs_raw[mask, 0].mean()) if mask.any() else None,
                                 "mean_true_class_probability": float(probs_raw[np.flatnonzero(mask), y_true[mask]].mean()) if mask.any() else None,
                                 "mean_normalized_entropy": float(entropy_labeled[mask].mean()) if mask.any() else None,
                                 "mean_debris_vs_best_other_margin": float(margin_debris[mask].mean()) if mask.any() else None})
    # Confidence and uncertainty distributions for unannotated and invalid
    # pixels are described separately; these values are never scored as errors.
    for group_name, score_groups in (("unlabeled_valid_imagery", unlabeled_valid_scores),
                                    ("invalid_imagery_all", invalid_scores)):
        flattened = {key: np.concatenate(parts) if parts else np.array([], dtype=np.float32)
                     for key, parts in score_groups.items()}
        top_summary = score_summary(flattened["max_confidence"])
        debris_summary = score_summary(flattened["debris_probability"])
        entropy_summary = score_summary(flattened["entropy"])
        uncertainty_rows.append({"group": group_name, "count": top_summary["count"],
                                 "mean_max_softmax": top_summary["mean"],
                                 "median_max_softmax": top_summary["percentiles"].get("50"),
                                 "p05_max_softmax": top_summary["percentiles"].get("5"),
                                 "p95_max_softmax": top_summary["percentiles"].get("95"),
                                 "mean_marine_debris_probability": debris_summary["mean"],
                                 "median_marine_debris_probability": debris_summary["percentiles"].get("50"),
                                 "p05_marine_debris_probability": debris_summary["percentiles"].get("5"),
                                 "p95_marine_debris_probability": debris_summary["percentiles"].get("95"),
                                 "mean_true_class_probability": None,
                                 "mean_normalized_entropy": entropy_summary["mean"],
                                 "median_normalized_entropy": entropy_summary["percentiles"].get("50"),
                                 "p05_normalized_entropy": entropy_summary["percentiles"].get("5"),
                                 "p95_normalized_entropy": entropy_summary["percentiles"].get("95"),
                                 "mean_debris_vs_best_other_margin": None})

    # Scene review candidates are ranked separately from pixel-level errors.
    positive_unlabeled = [r["marine_debris_predictions_unlabeled_valid"] for r in scene_rows]
    nonzero_unlabeled = [x for x in positive_unlabeled if x > 0]
    unlabeled_review_cutoff = float(np.percentile(nonzero_unlabeled, 90)) if nonzero_unlabeled else 0.0
    disagreement_values = [r["labeled_disagreement_rate"] for r in scene_rows if r["labeled_disagreement_rate"] is not None]
    disagreement_cutoff = float(np.percentile(disagreement_values, 90)) if disagreement_values else 1.0
    review_rows = []
    for row in scene_rows:
        reasons = []
        if row["marine_debris_ground_truth_pixels"]:
            reasons.append("contains labeled Marine Debris; inspect annotation/prediction agreement")
        if not row["marine_debris_ground_truth_pixels"] and row["marine_debris_predictions_unlabeled_valid"]:
            reasons.append("debris predictions occur in an ROI with no labeled debris; unlabeled pixels are not false positives")
        if row["marine_debris_predictions_unlabeled_valid"] >= unlabeled_review_cutoff > 0:
            reasons.append("top-decile debris predictions on unlabeled valid imagery")
        if row["marine_water_to_debris_labeled"]:
            reasons.append("labeled Marine Water pixels predicted as debris")
        if row["ship_to_debris_labeled"]:
            reasons.append("labeled Ship pixels predicted as debris")
        if row["foam_to_debris_labeled"]:
            reasons.append("labeled Foam pixels predicted as debris")
        if row["labeled_disagreement_rate"] is not None and row["labeled_disagreement_rate"] >= disagreement_cutoff:
            reasons.append("top-decile disagreement among labeled pixels")
        if reasons:
            review_rows.append({**row, "review_reasons": "; ".join(reasons),
                                "priority_note": "Manual review candidate only; official labels are unchanged."})

    class_confusion_rows = []
    spectral_rows = []
    spectral_mean = np.divide(spectral_sum, spectral_count[:, None], out=np.full_like(spectral_sum, np.nan), where=spectral_count[:, None] > 0)
    spectral_var = np.divide(spectral_sum_sq, spectral_count[:, None], out=np.full_like(spectral_sum_sq, np.nan), where=spectral_count[:, None] > 0) - spectral_mean ** 2
    spectral_std = np.sqrt(np.maximum(spectral_var, 0))
    for class_id, class_name in enumerate(CLASS_NAMES):
        ymask = y_true == class_id
        class_confusion_rows.append({
            "ground_truth_class": class_name, "labeled_support": int(ymask.sum()),
            "predicted_as_marine_debris": int(confusion_counts(y_true[ymask], y_pred[ymask])[:, 0].sum()) if ymask.any() else 0,
            "marine_debris_pixels_missed_as_this_class": int(np.count_nonzero((y_true == 0) & (y_pred == class_id))),
            "mean_p_marine_debris_on_ground_truth_class": float(probs_raw[ymask, 0].mean()) if ymask.any() else None,
            "mean_p_ground_truth_class": float(probs_raw[np.flatnonzero(ymask), y_true[ymask]].mean()) if ymask.any() else None,
            "mean_top_confidence_on_ground_truth_class": float(raw_top[ymask].mean()) if ymask.any() else None,
            "mean_normalized_entropy": float(entropy_labeled[ymask].mean()) if ymask.any() else None,
            **{f"mean_{band}_reflectance": float(spectral_mean[class_id, b]) if spectral_count[class_id] else None for b, band in enumerate(WAVELENGTH_BANDS)},
        })
        spectral_rows.append({"ground_truth_class": class_name, "labeled_valid_spectral_pixels": int(spectral_count[class_id]),
                              **{f"mean_{band}": float(spectral_mean[class_id, b]) if spectral_count[class_id] else None for b, band in enumerate(WAVELENGTH_BANDS)},
                              **{f"std_{band}": float(spectral_std[class_id, b]) if spectral_count[class_id] else None for b, band in enumerate(WAVELENGTH_BANDS)}})

    # Select representative scenes by distinct review signals, then regenerate
    # visual panels from validation imagery only.
    selected_scene_ids: list[str] = []
    selectors = [
        lambda r: r["marine_debris_false_positives_labeled"],
        lambda r: r["marine_debris_false_negatives_labeled"],
        lambda r: r["marine_debris_predictions_unlabeled_valid"],
        lambda r: r["marine_water_to_debris_labeled"],
        lambda r: r["ship_to_debris_labeled"],
        lambda r: r["foam_to_debris_labeled"],
        lambda r: r["marine_debris_ground_truth_pixels"],
        lambda r: r["mean_normalized_entropy_labeled"] or 0,
    ]
    for selector in selectors:
        chosen = max(scene_rows, key=selector)
        if chosen["roi"] not in selected_scene_ids and selector(chosen) > 0:
            selected_scene_ids.append(chosen["roi"])
    review_viz_rows = []
    for roi in selected_scene_ids:
        record = analyze_scene(dataset_root, roi, detector)
        filename = f"validation_{roi}.png"
        save_gallery(gallery_dir / filename, record)
        matching = next(row for row in scene_rows if row["roi"] == roi)
        review_viz_rows.append({"roi": roi, "image": f"visualizations/{filename}",
                                "debris_ground_truth_pixels": matching["marine_debris_ground_truth_pixels"],
                                "labeled_false_positives": matching["marine_debris_false_positives_labeled"],
                                "labeled_false_negatives": matching["marine_debris_false_negatives_labeled"],
                                "debris_predictions_on_unlabeled_valid_pixels": matching["marine_debris_predictions_unlabeled_valid"],
                                "marine_water_to_debris": matching["marine_water_to_debris_labeled"],
                                "ship_to_debris": matching["ship_to_debris_labeled"],
                                "foam_to_debris": matching["foam_to_debris_labeled"]})

    # Threshold PR tradeoff using validation rows only. A is restricted to the
    # current argmax debris pixels; B is the one-vs-rest P(debris) score.
    # Reconstruct per-pixel Strategy A confidence from labeled rows.
    # An argmax-debris pixel has p(debris)==max-softmax; otherwise its A score is 0.
    pr_a_score = np.where(np.concatenate(labeled_pred) == 0, max_conf, -1.0)
    pr_a_p, pr_a_r, _ = precision_recall_curve(true_debris.astype(np.uint8), pr_a_score)
    pr_b_p, pr_b_r, _ = precision_recall_curve(true_debris.astype(np.uint8), p_debris)

    threshold_analysis = {
        "dataset": "MARIDA", "dataset_version": DATASET_VERSION, "dataset_doi": DATASET_DOI,
        "archive_md5_observed": archive_md5, "archive_checksum_verified": archive_md5 is not None,
        "checkpoint_sha256": model_sha, "evaluation_split": "official val_X.txt only",
        "validation_scene_count": len(val_rois), "validation_train_overlap_count": 0,
        "test_split_accessed": False,
        "evaluation_date_utc": datetime.now(timezone.utc).isoformat(),
        "thresholds": THRESHOLDS,
        "strategies": {
            "max_softmax_argmax_debris": "Current class argmax must be Marine Debris and max softmax >= threshold; pixels below max-confidence threshold are abstained/uncertain.",
            "marine_debris_probability_one_vs_rest": "P(Marine Debris) >= threshold regardless of argmax; this is a binary class-specific override and can conflict with the highest-probability non-debris class.",
        },
        "label_policy": "0-valued official masks are unlabeled and excluded from precision/recall/F1/IoU. Predictions on unlabeled or invalid imagery are reported separately and never counted as false positives.",
        "invalid_imagery_policy": "Any masked or non-finite input band marks a pixel invalid. The model still receives mean-imputed inputs as local detector does; invalid pixel predictions are excluded from valid-imagery counts and reported separately.",
        "labeled_support": int(y_true.size),
        "labeled_valid_imagery_support": int(imagery_valid_labeled.sum()),
        "labeled_invalid_imagery_support": int((~imagery_valid_labeled).sum()),
        "overall_invalid_and_unlabeled_counts": invalid_counts,
        "threshold_rows": threshold_rows,
        "best_f1_validation_candidates_not_production": best_validation_thresholds,
        "marine_debris_precision_recall_curves": {
            "max_softmax_argmax_debris": {"precision": pr_a_p.tolist(), "recall": pr_a_r.tolist()},
            "marine_debris_probability_one_vs_rest": {"precision": pr_b_p.tolist(), "recall": pr_b_r.tolist()},
        },
        "temperature_scaling": {
            "fit": temp_fit,
            "before": calibration_before,
            "after_validation_fit_in_sample": calibration_after,
            "interpretation": "Exploratory scalar calibration fitted and scored on the same validation labels; use an independent calibration set or nested validation before deployment.",
        },
    }

    write_csv(output_dir / "threshold_analysis.csv", threshold_rows)
    write_csv(output_dir / "scene_level_metrics.csv", scene_rows)
    write_csv(output_dir / "uncertainty_analysis.csv", uncertainty_rows)
    write_csv(output_dir / "class_confusion_analysis.csv", class_confusion_rows)
    write_csv(output_dir / "spectral_confusion_profiles.csv", spectral_rows)
    write_csv(output_dir / "label_review_candidates.csv", review_rows)
    (output_dir / "threshold_analysis.json").write_text(json.dumps(threshold_analysis, indent=2), encoding="utf-8")
    (output_dir / "validation_confusion_matrix.csv").write_text(
        "true\\pred," + ",".join(CLASS_NAMES) + "\n" + "".join(
            name + "," + ",".join(str(int(x)) for x in row) + "\n"
            for name, row in zip(CLASS_NAMES, confusion)
        ), encoding="utf-8")

    # Threshold comparison chart with measured validation operating points.
    fig, ax = plt.subplots(figsize=(8, 6))
    for strategy, label, marker in (("max_softmax_argmax_debris", "A: argmax debris + max confidence", "o"),
                                    ("marine_debris_probability_one_vs_rest", "B: Marine Debris probability", "s")):
        selected = [r for r in threshold_rows if r["strategy"] == strategy and r["precision"] is not None]
        ax.plot([r["recall"] for r in selected], [r["precision"] for r in selected], marker=marker, label=label)
        for r in selected:
            if r["threshold"] in (0.3, 0.5, 0.7, 0.9):
                ax.annotate(f"{r['threshold']:.1f}", (r["recall"], r["precision"]), fontsize=7)
    ax.set(xlabel="Marine Debris recall (labeled validation pixels)", ylabel="Marine Debris precision (labeled validation pixels)",
           title="Validation-only threshold tradeoff", xlim=(0, 1), ylim=(0, 1))
    ax.grid(alpha=.3); ax.legend(); fig.tight_layout()
    fig.savefig(output_dir / "marine_debris_precision_recall.png", dpi=170); plt.close(fig)

    # Reliability diagrams are separate for top-label and debris one-vs-rest.
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), constrained_layout=True)
    for axis, raw_key, cal_key, title in (
        (axes[0], "raw_top_label", "temperature_scaled_top_label", "Top-label confidence"),
        (axes[1], "raw_marine_debris_ovr", "temperature_scaled_marine_debris_ovr", "Marine Debris one-vs-rest score"),
    ):
        for key, label, marker in ((raw_key, "Raw", "o"), (cal_key, "Temperature-scaled (fit on validation)", "s")):
            rows = reliability[key]
            points = [r for r in rows if r["count"]]
            axis.plot([r["mean_score"] for r in points], [r["observed_frequency"] for r in points], marker=marker, label=label)
        axis.plot([0, 1], [0, 1], linestyle="--", color="gray", label="Perfect reliability")
        axis.set(xlabel="Mean predicted score", ylabel="Observed frequency", title=title, xlim=(0, 1), ylim=(0, 1))
        axis.grid(alpha=.3); axis.legend(fontsize=8)
    fig.savefig(output_dir / "confidence_reliability_diagram.png", dpi=170); plt.close(fig)
    (output_dir / "reliability_bins.json").write_text(json.dumps(reliability, indent=2), encoding="utf-8")

    # Scene-level and review findings to support the report and manual QA.
    debris_scenes = sum(r["marine_debris_ground_truth_pixels"] > 0 for r in scene_rows)
    predicted_no_gt = sum(r["marine_debris_ground_truth_pixels"] == 0 and r["marine_debris_predictions_unlabeled_valid"] > 0 for r in scene_rows)
    high_prediction_scenes = sorted(scene_rows, key=lambda r: r["marine_debris_prediction_rate_valid_imagery"] or 0, reverse=True)[:10]
    highest_fp_scenes = sorted(scene_rows, key=lambda r: r["marine_debris_false_positives_labeled"], reverse=True)[:10]
    highest_fn_scenes = sorted(scene_rows, key=lambda r: r["marine_debris_false_negatives_labeled"], reverse=True)[:10]
    report = [
        "# MARIDA Stage 4 — validation-only debris threshold and uncertainty analysis", "",
        f"- Date (UTC): {threshold_analysis['evaluation_date_utc']}",
        f"- Dataset: MARIDA {DATASET_VERSION} ({DATASET_DOI}); archive MD5 {archive_md5 or 'not supplied'}.",
        f"- Checkpoint SHA-256: `{model_sha}`; split: official validation only (`val_X.txt`, {len(val_rois)} patches).",
        "- `test_X.txt`, test masks, test imagery, and Stage 3 test metrics were not read by this analysis script.",
        f"- Labeled pixels: {y_true.size:,}; valid-imagery labeled {imagery_valid_labeled.sum():,}; invalid-imagery labeled {(~imagery_valid_labeled).sum():,}.",
        f"- Invalid imagery pixels (masked or non-finite): {invalid_counts['invalid_pixels']:,} across validation; predictions there are counted separately, not scored as errors.",
        "- Ground-truth mask value 0 is unlabeled. Debris predictions on unlabeled pixels are manual-review signals only, never false positives.",
        "",
        "## Validation label and prediction coverage", "",
        f"- Patches with labeled Marine Debris: {debris_scenes}/328.",
        f"- Patches with debris predictions on valid imagery but no labeled debris: {predicted_no_gt}; these predictions require visual/annotation review rather than automatic FP labeling.",
        f"- Label review candidates: {len(review_rows)}; see `label_review_candidates.csv`.",
        "- Highest predicted debris rates and labeled FP/FN scene rankings are included in `threshold_analysis.json`; full scene metrics are in `scene_level_metrics.csv`.",
        "",
        "## Threshold strategies", "",
        "Strategy A keeps the original argmax class and abstains when maximum softmax is below the threshold. Strategy B is a distinct one-vs-rest rule: it predicts Marine Debris whenever P(debris) reaches threshold, even if another class has a higher score. B can override the 11-class argmax and is not a mutually exclusive calibrated segmentation output.",
        "Threshold metrics use labeled validation pixels only. Unlabeled and invalid-image prediction counts are separate columns. Candidate F1 thresholds below are validation experiments, not production selections.",
        "",
        "| Strategy | Candidate threshold | Precision | Recall | F1 | IoU | TP | FP | FN | Labeled excluded % |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for strategy, best in best_validation_thresholds.items():
        row = next(r for r in threshold_rows if r["strategy"] == strategy and r["threshold"] == best["threshold"])
        report.append(f"| {strategy} | {best['threshold']:.2f} | {best['precision']:.3f} | {best['recall']:.3f} | {best['f1']:.3f} | {best['iou']:.3f} | {row['true_positives']} | {row['false_positives']} | {row['false_negatives']} | {row['labeled_pixels_excluded_pct']:.2f}% |")
    report += [
        "",
        f"Raw argmax overall top-label accuracy={calibration_before['top_label_accuracy']:.3f}; this is not the debris metric. Debris threshold points and both precision-recall curves are in `threshold_analysis.csv` and `marine_debris_precision_recall.png`.",
        "Threshold curves are validation-only. No threshold was deployed or selected for production.",
        "",
        "## Calibration and uncertainty", "",
        f"- Validation NLL: {calibration_before['negative_log_likelihood']:.4f} raw; {calibration_after['negative_log_likelihood']:.4f} after temperature scaling (T={temperature:.4f}).",
        f"- Top-label ECE (15 bins): {calibration_before['top_label_ece_15_equal_width_bins']:.4f} raw; {calibration_after['top_label_ece_15_equal_width_bins']:.4f} scaled.",
        f"- Marine Debris OVR ECE: {calibration_before['marine_debris_ece_15_bins']:.4f} raw; {calibration_after['marine_debris_ece_15_bins']:.4f} scaled. OVR Brier: {calibration_before['marine_debris_one_vs_rest_brier']:.6f} raw; {calibration_after['marine_debris_one_vs_rest_brier']:.6f} scaled.",
        f"- Multiclass Brier: {calibration_before['multiclass_brier_score_sum_over_classes']:.4f} raw; {calibration_after['multiclass_brier_score_sum_over_classes']:.4f} scaled.",
        "- Temperature was fitted by bounded scalar minimization of multiclass NLL on validation labels and scored on those same labels. These are in-sample calibration results, not independent evidence for deployment.",
        "- Confidence distributions and entropy summaries by correctness, true class, debris outcome, unlabeled pixels, and invalid imagery are in `uncertainty_analysis.csv`.",
        "",
        "## Class confusion and spectral profiles", "",
        "Validation confusion and per-class probabilities are in `class_confusion_analysis.csv`. Per-class mean/std Sentinel-2 reflectance profiles are in `spectral_confusion_profiles.csv`. These are descriptive associations; they do not establish the cause of confusion.",
        "",
        "## Visual scene review", "",
        "`visualizations/` contains RGB, ground-truth labels, model prediction, debris probability, normalized entropy, and label-coverage panels for scenes selected by labeled FP/FN, unlabeled debris predictions, Marine Water/Ship/Foam confusion, debris label support, and uncertainty. Unlabeled/invalid areas are explicitly separated.",
        "",
        "## Evidence-based next work", "",
        "Keep production inference and its threshold unchanged pending independent evidence. Validation shows the threshold strategies create different precision/recall tradeoffs, but the same 328 scenes were used for exploration and temperature fitting. A later held-out calibration set or nested scene-level validation is needed before adopting a threshold or calibrator. The visual review candidates should be checked by annotators before any fine-tuning decision.",
        "",
        "| Option | Expected benefit | Risks | Data/complexity | Retraining? | Success evidence |",
        "|---|---|---|---|---|---|",
        "| Validation class-specific threshold | Tune debris recall/precision operating point | Overfit to sparse validation labels; can override competing class | Existing validation; low | No | Frozen operating point improves debris PR on independent scene holdout |",
        "| Probability calibration | More reliable scores for abstention/ranking | In-sample calibration may not transfer; rare debris distorts ECE | Independent calibration scenes; low-medium | No checkpoint retraining | Better held-out NLL/Brier/reliability without degrading detection utility |",
        "| Hard-example mining | Focus learning on water/ship/foam confusions | Repeats ambiguous/incorrect annotations and overfits scenes | Curated, reviewed hard examples; medium | Yes | Scene-held-out debris PR and confusion improve |",
        "| Class-weighted loss | Increase rare debris contribution | More false positives/unstable optimization | Rebalanced training evidence; medium | Yes | Debris F1/IoU improves without unacceptable false alarm burden |",
        "| Focal loss | Emphasize difficult/rare pixels | Can amplify label noise and hurt calibration | Reviewed masks and ablations; medium-high | Yes | Independent scene metrics beat current checkpoint and weighted-loss control |",
        "| More debris samples | Improve variation and support | More weak labels may add noise/domain bias | Diverse, independently labeled scenes; high | Yes | Better held-out geography/season performance |",
        "| Improved ground truth | Reduce uncertainty in sparse labels and review candidates | Expert effort; changing labels changes benchmark comparability | Expert review and versioned masks; high | Not initially | Inter-annotator agreement and evaluation sensitivity documented |",
        "| Fine-tune existing checkpoint | Adapt to validated OceanWatch input domain | Catastrophic forgetting/leakage/small-data overfit | More train/validation scenes; high | Yes | Scene-disjoint external test improvement with frozen protocol |",
        "| Independent coastal scenes | Measure domain generalization | Data collection and provenance burden | New verified imagery and expert labels; high | No | Performance reported by held-out site/season |",
        "",
        "## Scope and provenance", "",
        "This is an offline research analysis of official MARIDA validation data. It does not call the production upload API, register research imagery, alter source masks, change production settings, or modify weights.",
        "",
        "## Post-freeze Stage 3 reproducibility check", "",
        "After the validation threshold and calibration results were frozen, a separate regression run of the unchanged Stage 3 evaluator on the official test split reproduced the saved Stage 3 metrics exactly (359 scenes, 194,863 labeled pixels, and identical per-class, debris, confidence, and upstream/local comparison metrics). This check was not used to choose or modify any Stage 4 threshold or calibration result. The Stage 4 analysis above itself did not read test IDs, test imagery, or Stage 3 test metrics.",
    ]
    (output_dir / "report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    (output_dir / "scene_rankings.json").write_text(json.dumps({
        "validation_scene_count": len(scene_rows), "scenes_with_debris_labels": debris_scenes,
        "scenes_with_debris_predictions_but_no_debris_labels": predicted_no_gt,
        "highest_predicted_debris_rate": high_prediction_scenes,
        "highest_labeled_false_positive_counts": highest_fp_scenes,
        "highest_labeled_false_negative_counts": highest_fn_scenes,
        "visualized_scenes": review_viz_rows,
        "review_candidate_count": len(review_rows),
    }, indent=2), encoding="utf-8")
    return threshold_analysis


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-root", type=Path, default=BACKEND_DIR / "data")
    parser.add_argument("--archive", type=Path, default=BACKEND_DIR / "data" / "MARIDA.zip")
    parser.add_argument("--output-dir", type=Path, default=BACKEND_DIR / "evaluation" / "marida_stage4")
    args = parser.parse_args()
    result = evaluate(args.dataset_root, args.output_dir, args.archive)
    print(json.dumps({"validation_scene_count": result["validation_scene_count"],
                      "labeled_pixels": result["labeled_support"],
                      "best_validation_candidates": result["best_f1_validation_candidates_not_production"],
                      "temperature": result["temperature_scaling"]["fit"]["temperature"],
                      "output_dir": str(args.output_dir)}, indent=2))


if __name__ == "__main__":
    main()
