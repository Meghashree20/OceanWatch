# OceanWatch Stage 5 — independent validation and generalization assessment

## Executive finding

Independent Sentinel-2 annotation resources exist, but no external product/label archive was available locally and public Copernicus item-level queries could not be completed from this environment. Therefore independent threshold, calibration, paired-scene, and bootstrap metrics are **not estimable in this run**. No accuracy is inferred from unlabeled satellite imagery. Keep production behavior unchanged.

Checkpoint SHA-256: `7a690027cf279b31cae45a3188f2d4faa011b222f42b5e92c9ec6b1fd46d1b37`. Frozen candidates: Strategy A max-softmax 0.40; Strategy B direct P(debris) 0.35; temperature T=0.6118. Stage 4 validation metrics are included only as non-independent context in `independent_threshold_comparison.csv` and `calibration_comparison.csv`.

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

The local validation-only re-audit found 74,516 invalid pixels among 21,495,808 pixels in 328 patches (0.3467%). All 74,516 are non-finite samples; Rasterio masks flag none, and no invalid pixel overlaps a labeled class (including clouds). They occur in three adjacent patches from ROI scene `18-9-20_16PCC`: 18-9-20_16PCC_47 has 44,592 invalid pixels (68.04%), _48 has 29,864 (45.57%), and _50 has 60 (0.09%). The first two have large, contiguous diagonal regions spanning the patch interior; only 4,368/74,516 invalid pixels touch the outer four-pixel patch border. This looks like an internal source coverage/nodata gap rather than cloud labels, but its upstream cause cannot be proven from these TIFFs alone. See the per-patch masks and overlay figures. At frozen thresholds, Stage 4 separately reports 14 invalid-image predictions for A and 26 for B; valid-image prediction totals are 4,654 and 6,497 respectively. A rejects 1.176% of labeled pixels; invalid pixels have no labeled support. These invalid predictions are excluded from valid-image coverage denominators and are not scored as FP/FN. No invalid pixels were reassigned.

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

This run used local MARIDA `val_X.txt` only for invalid-pixel re-audit, did not read the MARIDA test split, and did not run inference or alter model/data/production code. Candidate thresholds and T are frozen from Stage 4; no tuning occurred. References are listed in the two inventory CSVs and linked here: FloatingObjects (https://github.com/ESA-PhiLab/floatingobjects), RefinedFloatingObjects and PLP (https://github.com/MarcCoru/marinedebrisdetector/blob/main/doc/data.md), Sentinel-2 debris evaluation study (https://arxiv.org/abs/2307.02465), and CDSE STAC (https://documentation.dataspace.copernicus.eu/APIs/STAC.html).
