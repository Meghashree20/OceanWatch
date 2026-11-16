# OceanWatch Stage 5 completion report

## 1. Executive summary

Stage 5 documentation and local validation-data integrity checks are complete. Independent external evaluation is **not complete**: no external image/reference-label archive or verified Copernicus product was obtained and evaluated. Independent sample counts are zero; no accuracy was inferred from unlabeled imagery and no results from other models are attributed to OceanWatch. Keep current production behavior unchanged.

## 2. Scope and research questions

This work checked whether public independent Sentinel-2 marine-debris labels are available, recorded published candidate scenes and unresolved product metadata for the four monitoring locations, verified the frozen Stage 4 candidate records, and re-audited the 74,516 invalid pixels in the official MARIDA validation patches. It did not perform external inference, choose thresholds, fit calibration, inspect the MARIDA test split, or alter production code.

## 3. Checkpoint identity and frozen configuration

- Checkpoint SHA-256: `7a690027cf279b31cae45a3188f2d4faa011b222f42b5e92c9ec6b1fd46d1b37`.
- Frozen Strategy A: retain class argmax only when maximum softmax is at least `0.40`; lower-confidence pixels abstain.
- Frozen Strategy B: direct Marine Debris score threshold `P(debris) >= 0.35`; this may override any other argmax class.
- Frozen temperature candidate: `T = 0.6118`, calibration analysis only.
- MARIDA class order, preprocessing, and production inference remain unchanged. No threshold was deployed.

## 4. MARIDA validation invalid-pixel audit

The audit read only the official `val_X.txt` manifest and its 328 image/mask patches. It found 74,516/21,495,808 invalid pixels (0.3467%) in three patches from one ROI scene. Every invalid pixel contains at least one non-finite band sample; Rasterio validity masks flag none. No invalid pixel overlaps any labeled class, including Clouds. Two patches contain large contiguous diagonal gaps (44,592 and 29,864 pixels); the third has 60 border pixels. This resembles an internal source coverage/nodata gap, but the source TIFFs alone do not establish the upstream cause. Invalid predictions are reported separately and excluded from valid-image coverage and labeled scoring. See `invalid_pixel_analysis.csv`, `invalid_pixel_summary.json`, and the visualizations.

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
