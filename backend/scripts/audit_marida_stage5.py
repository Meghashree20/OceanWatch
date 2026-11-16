"""Build Stage 5 research inventories and audit Stage 4 invalid pixels.

This report generator reads the official MARIDA validation manifest and its
imagery/masks only. It does not read test_X.txt, run model inference, tune a
threshold, or modify production inference or the checkpoint.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from scipy import ndimage

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
REPO_ROOT = BACKEND_DIR.parent
STAGE4_DIR = BACKEND_DIR / "evaluation" / "marida_stage4"
OUTPUT_DEFAULT = BACKEND_DIR / "evaluation" / "marida_stage5"
MODEL_SHA256 = "7a690027cf279b31cae45a3188f2d4faa011b222f42b5e92c9ec6b1fd46d1b37"
THRESHOLD_A = 0.40
THRESHOLD_B = 0.35
TEMPERATURE = 0.6118
CLASSES = [
    "Marine Debris", "Dense Sargassum", "Sparse Sargassum", "Natural Organic Material",
    "Ship", "Clouds", "Marine Water", "Sediment-Laden Water", "Foam", "Turbid Water",
    "Shallow Water",
]
SOURCES = {
    "floatingobjects": "https://github.com/ESA-PhiLab/floatingobjects",
    "floatingobjects_paper": "https://doi.org/10.5194/isprs-annals-V-3-2021-285-2021",
    "refined_data": "https://github.com/MarcCoru/marinedebrisdetector/blob/main/doc/data.md",
    "detector_paper": "https://arxiv.org/abs/2307.02465",
    "biermann": "https://doi.org/10.1038/s41598-020-62298-z",
    "duarte": "https://doi.org/10.1109/TGRS.2023.3283607",
    "cdse_stac": "https://stac.dataspace.copernicus.eu/v1/collections/sentinel-2-l2a",
    "cdse_docs": "https://documentation.dataspace.copernicus.eu/APIs/STAC.html",
}


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def read_validation_ids(root: Path) -> list[str]:
    manifest = root / "splits" / "val_X.txt"
    if not manifest.is_file():
        raise FileNotFoundError(f"Validation manifest not found: {manifest}")
    ids = [line.strip() for line in manifest.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    if len(ids) != 328 or len(set(ids)) != 328:
        raise ValueError(f"Expected 328 unique validation IDs, found {len(ids)}")
    return sorted(ids)


def roi_paths(root: Path, roi: str) -> tuple[Path, Path]:
    pieces = roi.split("_")
    folder = "_".join(["S2", *pieces[:-1]])
    filename = "_".join(["S2", *pieces])
    scene = root / "patches" / folder
    return scene / f"{filename}.tif", scene / f"{filename}_cl.tif"


def map_source_labels(labels: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    mapped = labels.astype(np.int16, copy=True)
    mapped[np.isin(mapped, (12, 13, 14, 15))] = 7
    mapped -= 1
    valid = labels != 0
    mapped[~valid] = -1
    return mapped, valid


def invalid_pixel_audit(root: Path, output: Path) -> dict[str, Any]:
    ids = read_validation_ids(root)
    rows: list[dict[str, Any]] = []
    aggregate_row = np.zeros(256, dtype=np.int64)
    aggregate_col = np.zeros(256, dtype=np.int64)
    aggregate_map = np.zeros((256, 256), dtype=np.float64)
    aggregate_count = 0
    total_invalid = total_pixels = total_invalid_labeled = 0
    invalid_class_counts = np.zeros(11, dtype=np.int64)
    per_band_masked = np.zeros(11, dtype=np.int64)
    per_band_nonfinite = np.zeros(11, dtype=np.int64)
    selected_maps: list[tuple[str, np.ndarray, np.ndarray]] = []

    for roi in ids:
        image_path, mask_path = roi_paths(root, roi)
        with rasterio.open(image_path) as ds:
            data = ds.read().astype(np.float32, copy=False)
            band_masked = ds.read_masks() == 0
        if data.shape != (11, 256, 256):
            raise ValueError(f"Unexpected image shape for {roi}: {data.shape}")
        nonfinite = ~np.isfinite(data)
        invalid = (band_masked | nonfinite).any(axis=0)
        with rasterio.open(mask_path) as ds:
            raw_labels = ds.read(1)
        labels, labeled = map_source_labels(raw_labels)
        n_invalid = int(invalid.sum())
        invalid_labeled = int((invalid & labeled).sum())
        total_invalid += n_invalid
        total_pixels += invalid.size
        total_invalid_labeled += invalid_labeled
        aggregate_count += 1
        aggregate_row += invalid.sum(axis=1)
        aggregate_col += invalid.sum(axis=0)
        aggregate_map += invalid
        per_band_masked += band_masked.sum(axis=(1, 2))
        per_band_nonfinite += nonfinite.sum(axis=(1, 2))
        for class_id in range(11):
            invalid_class_counts[class_id] += int((invalid & labeled & (labels == class_id)).sum())

        yy, xx = np.where(invalid)
        edge = np.zeros_like(invalid)
        edge[:4, :] = True
        edge[-4:, :] = True
        edge[:, :4] = True
        edge[:, -4:] = True
        components, component_count = ndimage.label(invalid, structure=np.ones((3, 3), dtype=np.uint8))
        if component_count:
            component_sizes = np.bincount(components.ravel())[1:]
            largest_component = int(component_sizes.max())
        else:
            largest_component = 0
        cloud_overlap = int((invalid & labeled & (labels == CLASSES.index("Clouds"))).sum())
        row = {
            "roi": roi,
            "scene_id": "_".join(roi.split("_")[:-1]),
            "patch_pixels": int(invalid.size),
            "invalid_pixels": n_invalid,
            "invalid_pct_patch": 100 * n_invalid / invalid.size,
            "invalid_labeled_pixels": invalid_labeled,
            "invalid_unlabeled_pixels": int((invalid & ~labeled).sum()),
            "invalid_overlaps_cloud_labels": cloud_overlap,
            "invalid_overlaps_other_labeled_classes": invalid_labeled - cloud_overlap,
            "invalid_on_outer_4_pixel_border": int((invalid & edge).sum()),
            "invalid_pct_on_outer_4_pixel_border": 100 * float((invalid & edge).sum()) / n_invalid if n_invalid else 0.0,
            "invalid_components_8_connected": int(component_count),
            "largest_invalid_component_pixels": largest_component,
            "invalid_row_min": int(yy.min()) if yy.size else None,
            "invalid_row_max": int(yy.max()) if yy.size else None,
            "invalid_col_min": int(xx.min()) if xx.size else None,
            "invalid_col_max": int(xx.max()) if xx.size else None,
            "masked_band_sample_count": int(band_masked.sum()),
            "nonfinite_band_sample_count": int(nonfinite.sum()),
            "interpretation": "Raster mask or non-finite source value; not assumed to be cloud unless independently labeled.",
        }
        rows.append(row)
        if n_invalid:
            selected_maps.append((roi, invalid, raw_labels))

    write_csv(output / "invalid_pixel_analysis.csv", rows)
    by_band = [{"band_index_1_based": i + 1, "masked_samples": int(per_band_masked[i]),
                "nonfinite_samples": int(per_band_nonfinite[i])} for i in range(11)]
    cloud_count = int(invalid_class_counts[CLASSES.index("Clouds")])
    np.savez_compressed(output / "invalid_pixel_spatial_summary.npz",
                        invalid_count_by_row=aggregate_row,
                        invalid_count_by_column=aggregate_col,
                        invalid_frequency_by_pixel=aggregate_map / aggregate_count)

    fig, axes = plt.subplots(1, 3, figsize=(15, 5), constrained_layout=True)
    axes[0].plot(np.arange(256), aggregate_row / aggregate_count)
    axes[0].set(title="Mean invalid pixels by row", xlabel="Pixel row", ylabel="Invalid pixels per patch")
    axes[1].plot(np.arange(256), aggregate_col / aggregate_count)
    axes[1].set(title="Mean invalid pixels by column", xlabel="Pixel column", ylabel="Invalid pixels per patch")
    axes[2].imshow(aggregate_map / aggregate_count, cmap="magma", vmin=0, vmax=1)
    axes[2].set(title="Fraction of validation patches invalid", xlabel="Pixel column", ylabel="Pixel row")
    fig.savefig(output / "visualizations" / "invalid_pixel_overview.png", dpi=160)
    plt.close(fig)
    if selected_maps:
        selected_maps.sort(key=lambda x: int(x[1].sum()), reverse=True)
        chosen = selected_maps[:4]
        fig, axes = plt.subplots(len(chosen), 2, figsize=(10, 3.1 * len(chosen)), squeeze=False, constrained_layout=True)
        for idx, (roi, invalid, raw_labels) in enumerate(chosen):
            axes[idx, 0].imshow(invalid, cmap="Reds", vmin=0, vmax=1)
            axes[idx, 0].set_title(f"{roi}: invalid mask")
            axes[idx, 1].imshow(raw_labels, cmap="tab20", interpolation="nearest")
            axes[idx, 1].imshow(np.ma.masked_where(~invalid, invalid), cmap="Reds", vmin=0, vmax=1, alpha=.7)
            axes[idx, 1].set_title("Official labels with invalid overlay")
            for ax in axes[idx]:
                ax.set_axis_off()
        fig.savefig(output / "visualizations" / "invalid_pixel_examples.png", dpi=160)
        plt.close(fig)

    summary = {
        "validation_patch_count": len(ids),
        "pixel_count": total_pixels,
        "invalid_pixels": total_invalid,
        "invalid_pixel_pct": 100 * total_invalid / total_pixels if total_pixels else None,
        "invalid_labeled_pixels": total_invalid_labeled,
        "invalid_unlabeled_pixels": total_invalid - total_invalid_labeled,
        "invalid_labeled_cloud_pixels": cloud_count,
        "invalid_labeled_noncloud_pixels": total_invalid_labeled - cloud_count,
        "invalid_pixels_touching_outer_4_pixel_border": int(sum(r["invalid_on_outer_4_pixel_border"] for r in rows)),
        "patches_with_invalid_pixels": sum(r["invalid_pixels"] > 0 for r in rows),
        "source_scenes_with_invalid_pixels": len({r["scene_id"] for r in rows if r["invalid_pixels"]}),
        "affected_patches": [{"roi": r["roi"], "invalid_pixels": r["invalid_pixels"],
                              "invalid_pct_patch": r["invalid_pct_patch"],
                              "invalid_on_outer_4_pixel_border": r["invalid_on_outer_4_pixel_border"],
                              "row_bounds": [r["invalid_row_min"], r["invalid_row_max"]],
                              "column_bounds": [r["invalid_col_min"], r["invalid_col_max"]]}
                             for r in rows if r["invalid_pixels"]],
        "frozen_candidate_prediction_counts": {},
        "band_counts": by_band,
        "semantics": "All invalid pixels arise from non-finite source samples; raster validity masks flag zero samples. Clouds are a semantic class, not automatically invalid imagery. The large contiguous diagonal regions resemble nodata/coverage gaps, but the TIFF metadata alone does not identify the upstream cause. No pixels are reassigned.",
    }
    if (STAGE4_DIR / "threshold_analysis.json").is_file():
        threshold_rows = json.loads((STAGE4_DIR / "threshold_analysis.json").read_text(encoding="utf-8"))["threshold_rows"]
        for strategy, threshold, label in (("max_softmax_argmax_debris", THRESHOLD_A, "A_0.40"),
                                           ("marine_debris_probability_one_vs_rest", THRESHOLD_B, "B_0.35")):
            match = next(r for r in threshold_rows if r["strategy"] == strategy and abs(r["threshold"] - threshold) < 1e-8)
            summary["frozen_candidate_prediction_counts"][label] = {
                "valid_imagery_predictions": match["predicted_debris_pixels_valid_imagery_all"],
                "invalid_imagery_predictions_separately_reported": match["predicted_debris_pixels_invalid_imagery"],
                "unlabeled_valid_predictions_separately_reported": match["predicted_debris_pixels_unlabeled_valid_imagery"],
                "labeled_pixels_excluded_pct": match["labeled_pixels_excluded_pct"],
            }
    (output / "invalid_pixel_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def dataset_inventory() -> list[dict[str, Any]]:
    return [
        {"dataset": "FloatingObjects", "independent_of_marida_checkpoint_training": "yes; separate Sentinel-2 source", "imagery": "26 globally distributed Sentinel-2 scenes", "labels": "3,297 line-annotated floating objects; water vs floating object in original schema", "annotation_quality": "coarse line labels; paper notes label noise", "processing_level_and_bands": "mixed source products; repo scene list includes L2A and non-L2A scenes; exact per-scene product metadata requires source files", "access": "public GitHub repository and linked download", "suitable_for_stage5": "screening/secondary independent test after per-scene harmonization; weak for debris-vs-natural class attribution", "blocker": "dataset archive not present locally; download/catalog access unavailable in this session", "source": SOURCES["floatingobjects"] + "; " + SOURCES["floatingobjects_paper"]},
        {"dataset": "RefinedFloatingObjects", "independent_of_marida_checkpoint_training": "yes; separate scenes and point annotations reported", "imagery": "six named scenes: Accra, Durban, Lagos, New Orleans, Venice, Marmara", "labels": "expert-reviewed point annotations for positive debris and difficult negatives; center points used for reported evaluation", "annotation_quality": "better localized than source lines; authors state class certainty differs by scene; selected Accra and Durban as likely plastic-bearing evaluation scenes", "processing_level_and_bands": "Sentinel-2; Accra L1C only in cited GEE source at publication; Durban L1C and L2A reported", "access": "public 1.3 GB compressed archive, 12 GB uncompressed", "suitable_for_stage5": "best candidate for point-level independent evaluation; not a full-scene segmentation benchmark; confirm checkpoint input preprocessing and scene overlap first", "blocker": "archive not downloaded; independent predictions/metrics not computed", "source": SOURCES["refined_data"] + "; " + SOURCES["detector_paper"]},
        {"dataset": "Plastic Litter Projects 2021/2022", "independent_of_marida_checkpoint_training": "yes; controlled deployed litter targets", "imagery": "Sentinel-2 scenes associated with target deployments in Greece", "labels": "deployed target locations with partial spectral unmixing/field context", "annotation_quality": "controlled positive target provenance; target detectability and representativeness differ from naturally accumulated debris", "processing_level_and_bands": "Sentinel-2 scene set; exact product details need archive manifest", "access": "public 38 MB compressed archive, 41 MB uncompressed", "suitable_for_stage5": "strong controlled positive check, paired with broad expert-reviewed negatives; does not by itself establish natural-scene operational precision", "blocker": "archive not downloaded; not evaluated", "source": SOURCES["refined_data"]},
        {"dataset": "Duarte-Azevedo spectral samples", "independent_of_marida_checkpoint_training": "yes; separate published dataset", "imagery": "Sentinel-2-derived per-pixel spectral samples", "labels": "water, plastic, driftwood, seaweed, pumice, sea snot, sea foam", "annotation_quality": "material-labelled samples compiled from literature/news/social reports; not a georeferenced exhaustive segmentation mask", "processing_level_and_bands": "ACOLITE DSF path-corrected reflectance; B9/B10 omitted from output", "access": "public GitHub dataset", "suitable_for_stage5": "spectral stress-test only; U-Net requires spatial context and cannot be evaluated directly on isolated spectra", "blocker": "not a spatial patch benchmark", "source": SOURCES["duarte"] + "; https://github.com/miguelmendesduarte/Floating-Marine-Debris-Data"},
        {"dataset": "MARIDA validation", "independent_of_marida_checkpoint_training": "validation split; not independent source domain", "imagery": "328 patches", "labels": "11-class weak-label segmentation", "annotation_quality": "official labels, sparse in debris", "processing_level_and_bands": "Sentinel-2 patch features; same MARIDA preparation family", "access": "local", "suitable_for_stage5": "Stage 4 frozen reference only; not independent evidence", "blocker": "not used as independent evaluation", "source": "10.5281/zenodo.5151941"},
    ]


def location_inventory() -> list[dict[str, Any]]:
    common_bands = "Sentinel-2 MSI has 13 bands at 10/20/60 m; OceanWatch MARIDA input requires B1,B2,B3,B4,B5,B6,B7,B8,B8A,B11,B12. Exact asset/calibration files must be checked on each product."
    return [
        {"location_id": "accra-coast", "location": "Accra Coast, Ghana", "latitude": 5.55, "longitude": -0.20,
         "query_aoi_bbox_wgs84": "-0.25,5.50,-0.15,5.60", "published_candidate_acquisition_date": "2018-10-31",
         "published_scene_id": "accra_20181031", "product_identifier": "not reported by source; CDSE item query unavailable", "tile_cloud_cover_pct": "not retrieved", "spatial_coverage": "published Sentinel-2 scene covers a debris outwash off Accra; exact product footprint unverified", "processing_level": "L1C only reported available in cited GEE source at publication; not L2A", "spectral_band_availability": common_bands, "reflectance_calibration_metadata": "L1C TOA; per-product quantification/offset metadata not retrieved", "annotation_status": "RefinedFloatingObjects point labels reported; independently curated, but archive not local", "suitability": "conditional point-level comparison after matching TOA preprocessing; not direct L2A evaluation", "catalog_query_status": "blocked: public catalog endpoint connection failed in this session", "source": SOURCES["detector_paper"] + "; " + SOURCES["biermann"]},
        {"location_id": "gulf-of-honduras", "location": "Gulf of Honduras", "latitude": 15.80, "longitude": -87.90,
         "query_aoi_bbox_wgs84": "-87.95,15.75,-87.85,15.85", "published_candidate_acquisition_date": "not established",
         "published_scene_id": "none identified in reviewed independent debris sources", "product_identifier": "not retrieved", "tile_cloud_cover_pct": "not retrieved", "spatial_coverage": "no intersecting Sentinel-2 product footprint verified", "processing_level": "not retrieved", "spectral_band_availability": common_bands, "reflectance_calibration_metadata": "not retrieved", "annotation_status": "no independent reference labels identified", "suitability": "catalog query and expert labels required", "catalog_query_status": "blocked: public catalog endpoint connection failed in this session", "source": SOURCES["cdse_stac"]},
        {"location_id": "durban-harbor", "location": "Durban Harbor, South Africa", "latitude": -29.86, "longitude": 31.02,
         "query_aoi_bbox_wgs84": "30.97,-29.91,31.07,-29.81", "published_candidate_acquisition_date": "2019-04-24",
         "published_scene_id": "durban_20190424", "product_identifier": "not reported by source; CDSE item query unavailable", "tile_cloud_cover_pct": "not retrieved", "spatial_coverage": "published Sentinel-2 scene covers harbor debris from April 2019 flood; exact product footprint unverified", "processing_level": "L1C and L2A both reported available; paper notes clouds/haze", "spectral_band_availability": common_bands, "reflectance_calibration_metadata": "BOA for L2A; exact per-product quantification/offset metadata not retrieved", "annotation_status": "RefinedFloatingObjects point labels and a specific Durban annotation archive are reported public; not local", "suitability": "promising independent point-level evaluation; cloud/haze and calibration harmonization must be handled", "catalog_query_status": "blocked: public catalog endpoint connection failed in this session", "source": SOURCES["detector_paper"] + "; " + SOURCES["biermann"]},
        {"location_id": "coastal-demo-site", "location": "Coastal Demo Site", "latitude": 12.91, "longitude": 74.85,
         "query_aoi_bbox_wgs84": "74.80,12.86,74.90,12.96", "published_candidate_acquisition_date": "not established",
         "published_scene_id": "none identified in reviewed independent debris sources", "product_identifier": "not retrieved", "tile_cloud_cover_pct": "not retrieved", "spatial_coverage": "no intersecting Sentinel-2 product footprint verified", "processing_level": "not retrieved", "spectral_band_availability": common_bands, "reflectance_calibration_metadata": "not retrieved", "annotation_status": "no independent reference labels identified", "suitability": "catalog query and expert labels required", "catalog_query_status": "blocked: public catalog endpoint connection failed in this session", "source": SOURCES["cdse_stac"]},
    ]


def frozen_comparison_outputs(output: Path) -> None:
    stage4 = json.loads((STAGE4_DIR / "threshold_analysis.json").read_text(encoding="utf-8"))
    threshold_rows = stage4["threshold_rows"]
    scene_rows = []
    with (STAGE4_DIR / "scene_level_metrics.csv").open(newline="", encoding="utf-8") as source:
        scene_rows = list(csv.DictReader(source))
    base_tp = sum(int(r["marine_debris_true_positives_labeled"]) for r in scene_rows)
    base_fp = sum(int(r["marine_debris_false_positives_labeled"]) for r in scene_rows)
    base_fn = sum(int(r["marine_debris_false_negatives_labeled"]) for r in scene_rows)
    base_support = sum(int(r["marine_debris_ground_truth_pixels"]) for r in scene_rows)
    base_predicted = base_tp + base_fp
    base_precision = base_tp / base_predicted if base_predicted else None
    base_recall = base_tp / base_support if base_support else None
    base_f1 = 2 * base_tp / (2 * base_tp + base_fp + base_fn) if 2 * base_tp + base_fp + base_fn else None
    base_iou = base_tp / (base_tp + base_fp + base_fn) if base_tp + base_fp + base_fn else None
    configs = [
        ("Original 11-class argmax", "max_softmax_argmax_debris", 0.0),
        ("Strategy A: argmax + max softmax >= 0.40", "max_softmax_argmax_debris", THRESHOLD_A),
        ("Strategy B: P(debris) >= 0.35", "marine_debris_probability_one_vs_rest", THRESHOLD_B),
    ]
    comparison = []
    for label, strategy, threshold in configs:
        row = next((r for r in threshold_rows if r["strategy"] == strategy and abs(r["threshold"] - threshold) < 1e-8), None)
        if threshold == 0.0:
            reference = {"precision": base_precision, "recall": base_recall, "f1": base_f1, "iou": base_iou,
                         "predicted": base_predicted, "excluded_pct": 0.0, "override_count": 0}
        else:
            reference = {"precision": row.get("precision") if row else None,
                         "recall": row.get("recall") if row else None,
                         "f1": row.get("f1") if row else None,
                         "iou": row.get("iou") if row else None,
                         "predicted": row.get("predicted_debris_pixels_labeled") if row else None,
                         "excluded_pct": row.get("labeled_pixels_excluded_pct") if row else None,
                         "override_count": row.get("class_probability_override_of_argmax_pixels_labeled", 0) if row else None}
        comparison.append({
            "configuration": label, "checkpoint_sha256": MODEL_SHA256,
            "independent_dataset": "not evaluated", "independent_scene_count": 0,
            "independent_precision": None, "independent_recall": None, "independent_f1": None,
            "independent_iou": None, "independent_fp": None, "independent_fn": None,
            "independent_predicted_debris_coverage_pct": None, "independent_rejected_labeled_pct": None,
            "marida_validation_reference_precision": reference["precision"],
            "marida_validation_reference_recall": reference["recall"],
            "marida_validation_reference_f1": reference["f1"],
            "marida_validation_reference_iou": reference["iou"],
            "marida_validation_reference_predicted_debris_labeled": reference["predicted"],
            "marida_validation_reference_rejected_labeled_pct": reference["excluded_pct"],
            "marida_validation_reference_B_override_pixels_labeled": reference["override_count"] if "Strategy B" in label else None,
            "independent_other_class_changes": None,
            "status": "Stage 4 validation-only reference; no independent labeled scene data were available locally; do not interpret reference values as independent generalization.",
        })
    write_csv(output / "independent_threshold_comparison.csv", comparison)

    scene_rows = [
        {"published_scene": "Accra 2018-10-31", "location": "Accra Coast, Ghana", "label_source": "RefinedFloatingObjects", "evaluation_unit": "annotated point", "independent_metrics_computed": "no", "reason": "Public annotations/image archive not downloaded; product harmonization and exact source id not verified."},
        {"published_scene": "Durban 2019-04-24", "location": "Durban Harbor, South Africa", "label_source": "RefinedFloatingObjects / Durban annotation archive", "evaluation_unit": "annotated point", "independent_metrics_computed": "no", "reason": "Public annotations/image archive not downloaded; exact source product id and L2A assets not verified."},
    ]
    write_csv(output / "scene_level_robustness.csv", scene_rows)
    ci_rows = []
    for cfg in ("Original argmax", "Strategy A 0.40", "Strategy B 0.35"):
        ci_rows.append({"configuration": cfg, "independent_scenes": 0, "metric": "precision/recall/F1/IoU paired scene delta", "estimate": None, "ci_2_5_pct": None, "ci_97_5_pct": None, "bootstrap_replicates": 0, "status": "not estimable: no independent image/label pairs locally; pixel bootstrap would be invalid"})
    write_csv(output / "statistical_confidence_intervals.csv", ci_rows)

    before = stage4["temperature_scaling"]["before"]
    after = stage4["temperature_scaling"]["after_validation_fit_in_sample"]
    cal_rows = []
    for label, summary in (("Raw softmax", before), ("Temperature-scaled; T=0.6118", after)):
        cal_rows.append({"configuration": label, "temperature": 1.0 if label == "Raw softmax" else TEMPERATURE,
                         "stage4_validation_nll": summary["negative_log_likelihood"],
                         "stage4_validation_multiclass_brier": summary["multiclass_brier_score_sum_over_classes"],
                         "stage4_validation_top_label_ece_15": summary["top_label_ece_15_equal_width_bins"],
                         "stage4_validation_debris_ovr_brier": summary["marine_debris_one_vs_rest_brier"],
                         "stage4_validation_debris_ovr_ece_15": summary["marine_debris_ece_15_bins"],
                         "independent_nll": None, "independent_multiclass_brier": None,
                         "independent_top_label_ece_15": None, "independent_debris_ovr_brier": None,
                         "independent_debris_ovr_ece_15": None,
                         "independent_sample_count": 0,
                         "interpretation": "MARIDA validation in-sample reference only; independent calibration generalization unmeasured."})
    write_csv(output / "calibration_comparison.csv", cal_rows)


def write_protocol_and_report(output: Path, invalid: dict[str, Any]) -> None:
    protocol = """# Expert annotation protocol for an independent Sentinel-2 marine-debris benchmark

## Scene selection and blinding

Select genuine Sentinel-2 L2A products from multiple coasts, seasons, turbidity regimes, river plumes, harbors, and offshore fronts. Include both suspected debris and deliberately selected difficult negatives. Retain full SAFE/STAC metadata, product ID, acquisition UTC, tile geometry, cloud percentage, processing baseline, quantification value, band offsets, and checksums. Keep sites and acquisition dates disjoint across train, validation, and locked test partitions. Do not use MARIDA-derived patches as independent observations.

## Imagery and interface

Show co-registered B4/B3/B2 natural color, B8/B4/B3 false color, B11/B8/B4, floating-debris indices as optional context, and individual visible/NIR/SWIR spectra. Preserve original reflectance values and per-band masks. The annotation interface must display scale, north arrow, acquisition/product metadata, and allow polygon/point labels, confidence, uncertainty polygons, and comments. Never display model predictions during first-pass annotation.

## Label ontology

Primary positive class: visible floating anthropogenic debris at the Sentinel-2 spatial support, including mixed litter accumulations where plastic is confirmed or probable. Record plastic certainty separately (confirmed / probable / unknown). Explicit negative classes: water; ships and wakes; foam/whitecaps; natural organic material/wood; dense and sparse Sargassum or other algae; sediment/turbidity; cloud/cloud shadow/haze; shoreline/land. Use an `uncertain` label for mixed/ambiguous objects and exclude uncertain pixels from headline accuracy while reporting their area and frequency.

## Independent annotation and adjudication

Two trained marine remote-sensing annotators independently label each candidate scene using imagery and independent contemporaneous evidence when available (field reports, deployed targets, geotagged photographs, or very-high-resolution reference acquired near the Sentinel-2 time). Do not use model-generated predictions as reference. Annotators record class, confidence (high/medium/low), polygon/point geometry, and evidence source. A third expert adjudicates disagreements without seeing model outputs. Report class-wise agreement, Dice/IoU on overlapping polygons, point agreement within a predeclared positional tolerance, and Cohen's kappa for categorical samples. Keep original annotations, adjudications, and revision history immutable and versioned.

## Evaluation lock

Before any inference, freeze the checkpoint hash, preprocessing, class map, Strategy A 0.40, Strategy B 0.35, and temperature T=0.6118. Score Strategy A and B only at valid labeled support; report A abstentions separately. Strategy B override pixels must be tabulated by the original argmax class and verified for false debris labels. Bootstrap whole acquisition scenes (and, if enough sites, sites as the outer cluster); never bootstrap pixels as independent samples. Publish per-scene data and confidence intervals. Keep final external test scenes inaccessible until all analysis code and decisions are frozen.
"""
    (output / "annotation_protocol.md").write_text(protocol, encoding="utf-8")

    report = f"""# OceanWatch Stage 5 — independent validation and generalization assessment

## Executive finding

Independent Sentinel-2 annotation resources exist, but no external product/label archive was available locally and public Copernicus item-level queries could not be completed from this environment. Therefore independent threshold, calibration, paired-scene, and bootstrap metrics are **not estimable in this run**. No accuracy is inferred from unlabeled satellite imagery. Keep production behavior unchanged.

Checkpoint SHA-256: `{MODEL_SHA256}`. Frozen candidates: Strategy A max-softmax 0.40; Strategy B direct P(debris) 0.35; temperature T=0.6118. Stage 4 validation metrics are included only as non-independent context in `independent_threshold_comparison.csv` and `calibration_comparison.csv`.

## Independent data availability

`FloatingObjects` provides 26 globally distributed Sentinel-2 scenes with 3,297 coarse line labels, but original labels are binary floating-object/water and the source paper notes label noise. It is useful as a secondary stress test, not a clean debris-vs-foam/wood/algae benchmark. `RefinedFloatingObjects` is the strongest candidate: six scenes have expert point labels, with Accra 2018-10-31 and Durban 2019-04-24 selected by its authors for likely plastic-containing debris evaluation; point labels support point-level classification metrics, not exhaustive segmentation metrics. Accra's cited source was L1C only; Durban L1C and L2A were reported. The Plastic Litter Projects provide controlled deployed-target scenes and are useful as a complementary positive check, but cannot alone represent naturally occurring debris or establish operational precision. A separate Duarte-Azevedo spectral dataset identifies plastic and natural floating materials but is per-pixel spectra without image context, so the U-Net cannot be evaluated directly against it.

The independent archives are public, but their imagery/labels were not locally available in this execution. We did not download multi-gigabyte archives or claim an evaluation from their published paper's results for a different model. See `independent_dataset_inventory.csv` for access, label semantics, processing caveats, and blockers.

## Four registered locations and imagery

The four registered IDs and coordinates are preserved. Published candidate acquisitions were found for Accra (2018-10-31; `accra_20181031`) and Durban (2019-04-24; `durban_20190424`). The reviewed paper reports Accra L1C only and both L1C/L2A for Durban, with clouds/haze in the Durban scene. No matching independent annotated acquisition was established for Gulf of Honduras or Coastal Demo Site. `four_location_imagery_inventory.csv` records the query AOIs and every unresolved metadata field.

The CDSE STAC/OData endpoints are documented for product discovery, but the API JSON endpoints were inaccessible from this session (direct catalog request closed its connection; browser search could not open the API result). Thus exact product IDs, tile cloud percentages, scene geometries, per-item band assets, calibration quantification/offset metadata, and current historical acquisition lists remain unverified for all four sites. “Not retrieved” does not mean no imagery exists. The four demo rasters remain unverified and are not registered or enabled.

## Independent threshold comparison and class effects

No independent image/label pairs were available locally; independent precision, recall, F1, IoU, FP/FN, predicted debris coverage, rejected-pixel percentage, other-class changes, and Strategy B override confusion are left blank. Strategy A, Strategy B and the original argmax are recorded in `independent_threshold_comparison.csv` with Stage 4 values clearly marked validation-only. `scene_level_robustness.csv` lists published Accra and Durban point-label candidates but does not present uncomputed scores as results. Strategy B's override rule needs an explicit per-original-class false-debris audit once those data are loaded.

## Calibration and statistical uncertainty

`calibration_comparison.csv` reports raw and temperature-scaled MARIDA validation in-sample values and leaves all independent metrics unavailable. No independent reliability diagram or generalization claim is possible. `statistical_confidence_intervals.csv` records that paired scene bootstrap intervals are not estimable at n=0. Once an independent sample exists, bootstrap by acquisition scene (and site where the number of sites supports it), not by pixel; correlated pixels do not provide independent sample size.

## Stage 4 invalid pixels

The local validation-only re-audit found {invalid['invalid_pixels']:,} invalid pixels among {invalid['pixel_count']:,} pixels in {invalid['validation_patch_count']} patches ({invalid['invalid_pixel_pct']:.4f}%). All 74,516 are non-finite samples; Rasterio masks flag none, and no invalid pixel overlaps a labeled class (including clouds). They occur in three adjacent patches from ROI scene `18-9-20_16PCC`: 18-9-20_16PCC_47 has 44,592 invalid pixels (68.04%), _48 has 29,864 (45.57%), and _50 has 60 (0.09%). The first two have large, contiguous diagonal regions spanning the patch interior; only 4,368/74,516 invalid pixels touch the outer four-pixel patch border. This looks like an internal source coverage/nodata gap rather than cloud labels, but its upstream cause cannot be proven from these TIFFs alone. See the per-patch masks and overlay figures. At frozen thresholds, Stage 4 separately reports 14 invalid-image predictions for A and 26 for B; valid-image prediction totals are 4,654 and 6,497 respectively. A rejects 1.176% of labeled pixels; invalid pixels have no labeled support. These invalid predictions are excluded from valid-image coverage denominators and are not scored as FP/FN. No invalid pixels were reassigned.

## Deployment readiness

| Configuration | Evidence | Research use | Operational monitoring |
|---|---|---|---|
| Original MARIDA argmax | Stage 3 MARIDA test and Stage 4 MARIDA validation; no new independent score | exploratory baseline | insufficient evidence for production debris alerts |
| Strategy A, 0.40 | Stage 4 validation only; abstains low maximum-softmax pixels | candidate for locked independent study | not ready; threshold was not independently checked |
| Strategy B, 0.35 | Stage 4 validation only; can override any other class | candidate for controlled point-level study with override audit | not ready; false debris overrides unmeasured |
| Temperature T=0.6118 | MARIDA validation in-sample improvement only | candidate calibration experiment | not ready; calibration transfer unmeasured |

No candidate has independent performance intervals, cross-site replication, or demonstrated operational false-alarm burden. Keep production inference, thresholds, confidence calculation, model, class mapping, normalization, provenance security, and monitoring locations unchanged.

## Remaining work / blockers

1. Obtain the RefinedFloatingObjects annotations and matching source rasters, verify licenses/checksums and that scene coordinates/date are disjoint from OceanWatch training.
2. Query CDSE STAC for each exact AOI; save product ID, acquisition time, footprint, cloud metadata, assets, processing baseline, reflectance scale/offset and checksum; inspect AOI-level clouds rather than relying solely on tile cloud percentage.
3. Harmonize L1C/L2A scenes with the checkpoint's verified preprocessing, preserving native masks; prefer L2A when available and treat L1C as a separate domain.
4. Obtain expert labels for Gulf of Honduras and the Coastal Demo Site, plus difficult negatives (ships, wakes, foam, organic matter, sargassum, turbid water).
5. Freeze protocol, run A/B/T on the external labels, report Strategy B overrides by original class, per-scene metrics and scene/site bootstrap intervals.

## Provenance and scope

This run used local MARIDA `val_X.txt` only for invalid-pixel re-audit, did not read the MARIDA test split, and did not run inference or alter model/data/production code. Candidate thresholds and T are frozen from Stage 4; no tuning occurred. References are listed in the two inventory CSVs and linked here: FloatingObjects ({SOURCES['floatingobjects']}), RefinedFloatingObjects and PLP ({SOURCES['refined_data']}), Sentinel-2 debris evaluation study ({SOURCES['detector_paper']}), and CDSE STAC ({SOURCES['cdse_docs']}).
"""
    (output / "deployment_readiness_report.md").write_text(report, encoding="utf-8")

    completion_report = f"""# OceanWatch Stage 5 completion report

## 1. Executive summary

Stage 5 documentation and local validation-data integrity checks are complete. Independent external evaluation is **not complete**: no external image/reference-label archive or verified Copernicus product was obtained and evaluated. Independent sample counts are zero; no accuracy was inferred from unlabeled imagery and no results from other models are attributed to OceanWatch. Keep current production behavior unchanged.

## 2. Scope and research questions

This work checked whether public independent Sentinel-2 marine-debris labels are available, recorded published candidate scenes and unresolved product metadata for the four monitoring locations, verified the frozen Stage 4 candidate records, and re-audited the 74,516 invalid pixels in the official MARIDA validation patches. It did not perform external inference, choose thresholds, fit calibration, inspect the MARIDA test split, or alter production code.

## 3. Checkpoint identity and frozen configuration

- Checkpoint SHA-256: `{MODEL_SHA256}`.
- Frozen Strategy A: retain class argmax only when maximum softmax is at least `0.40`; lower-confidence pixels abstain.
- Frozen Strategy B: direct Marine Debris score threshold `P(debris) >= 0.35`; this may override any other argmax class.
- Frozen temperature candidate: `T = 0.6118`, calibration analysis only.
- MARIDA class order, preprocessing, and production inference remain unchanged. No threshold was deployed.

## 4. MARIDA validation invalid-pixel audit

The audit read only the official `val_X.txt` manifest and its 328 image/mask patches. It found {invalid['invalid_pixels']:,}/{invalid['pixel_count']:,} invalid pixels ({invalid['invalid_pixel_pct']:.4f}%) in three patches from one ROI scene. Every invalid pixel contains at least one non-finite band sample; Rasterio validity masks flag none. No invalid pixel overlaps any labeled class, including Clouds. Two patches contain large contiguous diagonal gaps (44,592 and 29,864 pixels); the third has 60 border pixels. This resembles an internal source coverage/nodata gap, but the source TIFFs alone do not establish the upstream cause. Invalid predictions are reported separately and excluded from valid-image coverage and labeled scoring. See `invalid_pixel_analysis.csv`, `invalid_pixel_summary.json`, and the visualizations.

## 5. Stage 4 thresholds and calibration (non-independent context)

All following values are MARIDA validation in-sample results, not external generalization evidence:

| Configuration | Precision | Recall | F1 | IoU | TP / FP / FN |
|---|---:|---:|---:|---:|---:|
| Original 11-class argmax | 0.6856 | 0.7079 | 0.6966 | 0.5344 | 761 / 349 / 314 |
| Strategy A, 0.40 | 0.7746 | 0.6744 | 0.7210 | 0.5638 | 725 / 211 / 350 |
| Strategy B, 0.35 | 0.7361 | 0.7163 | 0.7261 | 0.5699 | 770 / 276 / 305 |

Strategy A rejected 1.176% of labeled validation pixels. Strategy B made 33 labeled decisions where the original argmax was a different class at this operating point. Predictions over unlabeled pixels are not counted as false positives. At the frozen thresholds, A has 4,654 valid-image debris predictions and 14 invalid-image predictions; B has 6,497 valid-image and 26 invalid-image predictions. These are MARIDA validation coverage counts, not real-world performance.

For temperature scaling, MARIDA validation NLL changed from 0.24046 to 0.18162, multiclass Brier from 0.10529 to 0.09816, top-label ECE from 0.08263 to 0.03415, and debris one-vs-rest ECE from 0.00600 to 0.00109. The temperature was fitted and evaluated on the same validation labels. This does not establish independent calibration or justify changing production confidence.

## 6. Independent datasets and annotation limits

Public candidate sources include FloatingObjects (26 Sentinel-2 scenes, coarse line annotations and a binary floating-object/water label), RefinedFloatingObjects (six scenes with localized point annotations), and the Plastic Litter Projects (controlled deployed litter targets). They are candidates for a separate benchmark, but their archives were not downloaded here. The point labels do not provide exhaustive segmentation masks; FloatingObjects has label-noise/material-attribution limits; controlled targets do not by themselves represent natural pollution. A separate spectral-sample set lacks the spatial patches required by this U-Net. MARIDA validation is not an independent source domain.

No independent inference metrics, class effects, Strategy B override confusion, calibration scores, or external reliability diagram were computed. The empty independent metric fields in the CSVs mean unavailable, not zero performance.

## 7. Four-location imagery availability

All registered monitoring locations and coordinates remain preserved:

| Location | Registered coordinates | Published candidate | Verification status |
|---|---|---|---|
| Accra Coast, Ghana | 5.55, -0.20 | Sentinel-2 scene dated 2018-10-31 (`accra_20181031`) | Published source reports L1C only at the cited GEE source; no product ID, cloud percentage, exact footprint, or calibration metadata retrieved. |
| Gulf of Honduras | 15.80, -87.90 | No matching candidate established in reviewed independent debris sources | CDSE catalog item search and independent labels unresolved. |
| Durban Harbor, South Africa | -29.86, 31.02 | Sentinel-2 scene dated 2019-04-24 (`durban_20190424`) | Published source reports L1C and L2A; clouds/haze noted. Exact product ID, cloud percentage, footprint, band assets and calibration metadata not retrieved. |
| Coastal Demo Site | 12.91, 74.85 | No matching candidate established in reviewed independent debris sources | CDSE catalog item search and independent labels unresolved. |

These are published scene references, not products downloaded or verified for OceanWatch. CDSE STAC/OData JSON requests failed from this environment. `four_location_imagery_inventory.csv` records unresolved fields; no demo image was marked production-ready or registered.

Sentinel-2 MSI has 13 spectral bands at 10, 20, and 60 m; the OceanWatch MARIDA input uses B1, B2, B3, B4, B5, B6, B7, B8, B8A, B11, and B12. Exact assets and reflectance quantification/offset metadata remain unverified for each item. L1C is top-of-atmosphere reflectance and L2A is bottom-of-atmosphere reflectance; those processing domains must not be mixed without explicit harmonization.

## 8. Statistical confidence intervals

Independent scene count is zero, so paired-scene comparisons and scene/site bootstrap confidence intervals are not estimable. Pixel bootstrap is inappropriate because neighboring image pixels are correlated. `statistical_confidence_intervals.csv` leaves metric estimates and interval bounds empty and records zero independent scenes.

## 9. Deployment-readiness assessment

| Candidate | Research status | Operational readiness |
|---|---|---|
| Original MARIDA inference | Baseline for exploratory use; MARIDA-only evidence | Insufficient independent evidence for operational debris alerts |
| Strategy A, 0.40 | Frozen candidate for a locked external study | Not ready; independent threshold behavior unmeasured |
| Strategy B, 0.35 | Frozen candidate; requires per-original-class override and false-alarm audit | Not ready; independent override confusion unmeasured |
| Temperature T=0.6118 | In-sample calibration candidate only | Not ready; calibration transfer unmeasured |

No independent precision/recall interval, cross-site replication, or operational false-alarm burden is available. Do not change production inference, confidence calculation, thresholds, model, normalization, class mapping, provenance controls, or registered locations.

## 10. Blockers and next research steps

1. Obtain and checksum the RefinedFloatingObjects point labels and matching Sentinel-2 rasters; verify site/date independence from OceanWatch training.
2. Query CDSE for exact products at each AOI and preserve item ID, acquisition time, footprint, cloud metadata, assets, processing baseline, reflectance scale/offset, and checksums. Inspect AOI-level cloud/haze, not only tile-level cloud percentage.
3. Harmonize L1C and L2A as separate input domains against the frozen model preprocessing.
4. Obtain expert-reviewed positive and difficult-negative labels for Gulf of Honduras and the Coastal Demo Site.
5. Lock code and evaluate A/B/T on external labeled scenes; report point-level and scene-level limitations, per-class B overrides, scene-level metrics, and scene/site bootstrap intervals.

## 11. Reproduction commands and artifact inventory

From the repository root, the local audit can be reproduced with:

```powershell
& ./backend/.venv-stage25/Scripts/python.exe ./backend/scripts/audit_marida_stage5.py --dataset-root ./backend/data --output-dir ./backend/evaluation/marida_stage5
```

It requires the local official MARIDA validation patches and consumes the frozen Stage 4 outputs. It reads `val_X.txt` only and does not access `test_X.txt`.

The Stage 5 directory contains:

- `independent_dataset_inventory.csv`, `four_location_imagery_inventory.csv`
- `independent_threshold_comparison.csv`, `scene_level_robustness.csv`, `statistical_confidence_intervals.csv`, `calibration_comparison.csv`
- `invalid_pixel_analysis.csv`, `invalid_pixel_summary.json`, `invalid_pixel_spatial_summary.npz`
- `annotation_protocol.md`, `deployment_readiness_report.md`, `report.md`
- `visualizations/invalid_pixel_overview.png`, `visualizations/invalid_pixel_examples.png`

The audit generator is `backend/scripts/audit_marida_stage5.py`. Backend regression command: `./.venv-stage25/Scripts/python.exe -m pytest -q` from `backend`. Frontend regression commands: `npm.cmd test`, `npm.cmd run typecheck`, and `npm.cmd run build` from `frontend`.

## Provenance

The local audit used MARIDA `val_X.txt` only. It did not load the test manifest or imagery, did not fit thresholds or temperature, and did not modify checkpoint/model preprocessing, production code, location records, or Stage 3/4 scientific results. External validation remains blocked by unavailable local archives and unverified catalogue products.
"""
    (output / "report.md").write_text(completion_report, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-root", type=Path, default=BACKEND_DIR / "data")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DEFAULT)
    args = parser.parse_args()
    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    viz = output / "visualizations"
    viz.mkdir(exist_ok=True)

    invalid = invalid_pixel_audit(args.dataset_root, output)
    write_csv(output / "independent_dataset_inventory.csv", dataset_inventory())
    write_csv(output / "four_location_imagery_inventory.csv", location_inventory())
    frozen_comparison_outputs(output)
    write_protocol_and_report(output, invalid)
    print(json.dumps({"output_dir": str(output), "checkpoint_sha256": MODEL_SHA256,
                      "invalid_pixel_summary": invalid,
                      "independent_scene_metrics_computed": 0}, indent=2))


if __name__ == "__main__":
    main()
