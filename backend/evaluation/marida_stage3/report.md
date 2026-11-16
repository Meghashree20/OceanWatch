# MARIDA U-Net scientific evaluation

- Evaluation date (UTC): 2026-11-15T07:53:33.153276+00:00
- Dataset: MARIDA 1.0.0 (10.5281/zenodo.5151941); CC BY 4.0
- Official test split: 359 of 1,381 patches; 194,863 labeled pixels; 0-valued mask pixels ignored
- Paper-reported test labeled pixel count: 194,843 (release masks differ by +20)
- Archive MD5: 9bf32266f6e3711c9dfa3699b856c76f (verified=True)
- Checkpoint SHA-256: `7a690027cf279b31cae45a3188f2d4faa011b222f42b5e92c9ec6b1fd46d1b37`
- Device: cpu; inputs: 11 bands in MARIDA order, 256×256; source labels 12–15 aggregated to Marine Water
- Attribution: Kikaki et al. (2022), PLOS ONE 17(1):e0262247, DOI 10.1371/journal.pone.0262247.
- Upstream evaluation reference: [8de83a3394edfbe867d9fa825439666369ec6282](https://github.com/marine-debris/marine-debris.github.io/tree/8de83a3394edfbe867d9fa825439666369ec6282/semantic_segmentation/unet).

## Overall and marine debris results

- Pixel accuracy: 0.8952; mean IoU: 0.5702; macro F1: 0.6904; support-weighted F1: 0.8948.
- Marine debris: P 0.3920; R 0.6955; F1 0.5014; IoU 0.3346; support 381; TP/FP/FN 265/411/116.
- False-positive debris pixels are 0.2109% of labeled pixels and 0.2113% of labeled non-debris pixels.
- Debris labels occur in 101 scenes; 258 scenes have no labeled debris. Scene-wise rates for tiny supports are unstable.

## Per-class metrics

| Class | Support | TP | FP | FN | Precision | Recall | F1 | IoU |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Marine Debris | 381 | 265 | 411 | 116 | 0.3920 | 0.6955 | 0.5014 | 0.3346 |
| Dense Sargassum | 760 | 454 | 2 | 306 | 0.9956 | 0.5974 | 0.7467 | 0.5958 |
| Sparse Sargassum | 881 | 784 | 311 | 97 | 0.7160 | 0.8899 | 0.7935 | 0.6577 |
| Natural Organic Material | 49 | 1 | 4 | 48 | 0.2000 | 0.0204 | 0.0370 | 0.0189 |
| Ship | 1,174 | 892 | 269 | 282 | 0.7683 | 0.7598 | 0.7640 | 0.6182 |
| Clouds | 32,843 | 20,303 | 162 | 12,540 | 0.9921 | 0.6182 | 0.7617 | 0.6151 |
| Marine Water | 30,619 | 26,807 | 13,575 | 3,812 | 0.6638 | 0.8755 | 0.7551 | 0.6066 |
| Sediment-Laden Water | 93,037 | 92,356 | 86 | 681 | 0.9991 | 0.9927 | 0.9959 | 0.9918 |
| Foam | 387 | 212 | 1 | 175 | 0.9953 | 0.5478 | 0.7067 | 0.5464 |
| Turbid Water | 32,226 | 30,680 | 4,362 | 1,546 | 0.8755 | 0.9520 | 0.9122 | 0.8385 |
| Shallow Water | 2,506 | 1,683 | 1,243 | 823 | 0.5752 | 0.6716 | 0.6197 | 0.4489 |

## Confusion matrix (rows=true, columns=predicted)

| True \ Predicted | Marine Debris | Dense Sargassum | Sparse Sargassum | Natural Organic Material | Ship | Clouds | Marine Water | Sediment-Laden Water | Foam | Turbid Water | Shallow Water |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Marine Debris | 265 | 0 | 0 | 0 | 0 | 1 | 115 | 0 | 0 | 0 | 0 |
| Dense Sargassum | 1 | 454 | 304 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Sparse Sargassum | 17 | 2 | 784 | 0 | 0 | 0 | 78 | 0 | 0 | 0 | 0 |
| Natural Organic Material | 34 | 0 | 4 | 1 | 0 | 0 | 10 | 0 | 0 | 0 | 0 |
| Ship | 99 | 0 | 0 | 0 | 892 | 0 | 163 | 1 | 0 | 19 | 0 |
| Clouds | 43 | 0 | 0 | 0 | 8 | 20,303 | 12,250 | 12 | 0 | 22 | 205 |
| Marine Water | 190 | 0 | 1 | 0 | 192 | 68 | 26,807 | 0 | 1 | 3,352 | 8 |
| Sediment-Laden Water | 0 | 0 | 0 | 3 | 0 | 13 | 75 | 92,356 | 0 | 590 | 0 |
| Foam | 25 | 0 | 0 | 0 | 69 | 44 | 18 | 2 | 212 | 17 | 0 |
| Turbid Water | 0 | 0 | 0 | 0 | 0 | 0 | 450 | 66 | 0 | 30,680 | 1,030 |
| Shallow Water | 2 | 0 | 2 | 0 | 0 | 36 | 416 | 5 | 0 | 362 | 1,683 |

## Confidence and threshold behavior

Mean maximum softmax: 0.8116; correct pixels: 0.8397; incorrect pixels: 0.5714; predicted debris: 0.5458.
Top-label ECE (15 bins): 0.0836; multiclass Brier: 0.1613. Softmax is not claimed to be calibrated.
Threshold sensitivity is in `marine_debris_confidence_thresholds.csv`; 0.5 gives precision 0.5278 and recall 0.4987 under the existing maximum-softmax abstention rule. The production threshold is unchanged.

## Upstream/local consistency
359 scenes compared. Logits and probabilities are equal (maximum absolute difference 0.0); predicted classes match for 23,527,424/23,527,424 pixels. Official dimensions are stride-compatible, so no padding is used. The upstream implementation does not define the local replicate-pad/crop extension for nonstandard dimensions.

A separate, non-scoring 255×257 shape probe produced local replicate-padding to 256×272 and cropping back to 255×257; the pinned upstream model raised a skip-connection tensor-size mismatch. This shape probe was not included in any accuracy metric.

## Scene examples and outputs
- Complete per-scene table: `per_scene_metrics.csv`; highest false-positive and false-negative rates are also listed in `metrics.json`.
- Dataset label support across train/validation/test (descriptive only; no training or threshold selection): `dataset_label_counts_by_split.csv`.
- Confusion matrix: `confusion_matrix.csv` and `confusion_matrix.png`.
- Debris PR and confidence plots: `marine_debris_precision_recall.png`, `confidence_distribution.png`.
- Representative ground truth/prediction/RGB comparisons and false-positive/false-negative cases are in `visualizations/`.
- This is sparse weak-label pixel segmentation evaluation, not object-level detection accuracy or a geographic generalization claim.
