# MARIDA Stage 4 — validation-only debris threshold and uncertainty analysis

- Date (UTC): 2026-11-15T09:02:31.822141+00:00
- Dataset: MARIDA 1.0.0 (10.5281/zenodo.5151941); archive MD5 9bf32266f6e3711c9dfa3699b856c76f.
- Checkpoint SHA-256: `7a690027cf279b31cae45a3188f2d4faa011b222f42b5e92c9ec6b1fd46d1b37`; split: official validation only (`val_X.txt`, 328 patches).
- `test_X.txt`, test masks, test imagery, and Stage 3 test metrics were not read by this analysis script.
- Labeled pixels: 213,102; valid-imagery labeled 213,102; invalid-imagery labeled 0.
- Invalid imagery pixels (masked or non-finite): 74,516 across validation; predictions there are counted separately, not scored as errors.
- Ground-truth mask value 0 is unlabeled. Debris predictions on unlabeled pixels are manual-review signals only, never false positives.

## Validation label and prediction coverage

- Patches with labeled Marine Debris: 82/328.
- Patches with debris predictions on valid imagery but no labeled debris: 115; these predictions require visual/annotation review rather than automatic FP labeling.
- Label review candidates: 229; see `label_review_candidates.csv`.
- Highest predicted debris rates and labeled FP/FN scene rankings are included in `threshold_analysis.json`; full scene metrics are in `scene_level_metrics.csv`.

## Threshold strategies

Strategy A keeps the original argmax class and abstains when maximum softmax is below the threshold. Strategy B is a distinct one-vs-rest rule: it predicts Marine Debris whenever P(debris) reaches threshold, even if another class has a higher score. B can override the 11-class argmax and is not a mutually exclusive calibrated segmentation output.
Threshold metrics use labeled validation pixels only. Unlabeled and invalid-image prediction counts are separate columns. Candidate F1 thresholds below are validation experiments, not production selections.

| Strategy | Candidate threshold | Precision | Recall | F1 | IoU | TP | FP | FN | Labeled excluded % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| max_softmax_argmax_debris | 0.40 | 0.775 | 0.674 | 0.721 | 0.564 | 725 | 211 | 350 | 1.18% |
| marine_debris_probability_one_vs_rest | 0.35 | 0.736 | 0.716 | 0.726 | 0.570 | 770 | 276 | 305 | 0.00% |

Raw argmax overall top-label accuracy=0.938; this is not the debris metric. Debris threshold points and both precision-recall curves are in `threshold_analysis.csv` and `marine_debris_precision_recall.png`.
Threshold curves are validation-only. No threshold was deployed or selected for production.

## Calibration and uncertainty

- Validation NLL: 0.2405 raw; 0.1816 after temperature scaling (T=0.6118).
- Top-label ECE (15 bins): 0.0826 raw; 0.0342 scaled.
- Marine Debris OVR ECE: 0.0060 raw; 0.0011 scaled. OVR Brier: 0.002236 raw; 0.002119 scaled.
- Multiclass Brier: 0.1053 raw; 0.0982 scaled.
- Temperature was fitted by bounded scalar minimization of multiclass NLL on validation labels and scored on those same labels. These are in-sample calibration results, not independent evidence for deployment.
- Confidence distributions and entropy summaries by correctness, true class, debris outcome, unlabeled pixels, and invalid imagery are in `uncertainty_analysis.csv`.

## Class confusion and spectral profiles

Validation confusion and per-class probabilities are in `class_confusion_analysis.csv`. Per-class mean/std Sentinel-2 reflectance profiles are in `spectral_confusion_profiles.csv`. These are descriptive associations; they do not establish the cause of confusion.

## Visual scene review

`visualizations/` contains RGB, ground-truth labels, model prediction, debris probability, normalized entropy, and label-coverage panels for scenes selected by labeled FP/FN, unlabeled debris predictions, Marine Water/Ship/Foam confusion, debris label support, and uncertainty. Unlabeled/invalid areas are explicitly separated.

## Evidence-based next work

Keep production inference and its threshold unchanged pending independent evidence. Validation shows the threshold strategies create different precision/recall tradeoffs, but the same 328 scenes were used for exploration and temperature fitting. A later held-out calibration set or nested scene-level validation is needed before adopting a threshold or calibrator. The visual review candidates should be checked by annotators before any fine-tuning decision.

| Option | Expected benefit | Risks | Data/complexity | Retraining? | Success evidence |
|---|---|---|---|---|---|
| Validation class-specific threshold | Tune debris recall/precision operating point | Overfit to sparse validation labels; can override competing class | Existing validation; low | No | Frozen operating point improves debris PR on independent scene holdout |
| Probability calibration | More reliable scores for abstention/ranking | In-sample calibration may not transfer; rare debris distorts ECE | Independent calibration scenes; low-medium | No checkpoint retraining | Better held-out NLL/Brier/reliability without degrading detection utility |
| Hard-example mining | Focus learning on water/ship/foam confusions | Repeats ambiguous/incorrect annotations and overfits scenes | Curated, reviewed hard examples; medium | Yes | Scene-held-out debris PR and confusion improve |
| Class-weighted loss | Increase rare debris contribution | More false positives/unstable optimization | Rebalanced training evidence; medium | Yes | Debris F1/IoU improves without unacceptable false alarm burden |
| Focal loss | Emphasize difficult/rare pixels | Can amplify label noise and hurt calibration | Reviewed masks and ablations; medium-high | Yes | Independent scene metrics beat current checkpoint and weighted-loss control |
| More debris samples | Improve variation and support | More weak labels may add noise/domain bias | Diverse, independently labeled scenes; high | Yes | Better held-out geography/season performance |
| Improved ground truth | Reduce uncertainty in sparse labels and review candidates | Expert effort; changing labels changes benchmark comparability | Expert review and versioned masks; high | Not initially | Inter-annotator agreement and evaluation sensitivity documented |
| Fine-tune existing checkpoint | Adapt to validated OceanWatch input domain | Catastrophic forgetting/leakage/small-data overfit | More train/validation scenes; high | Yes | Scene-disjoint external test improvement with frozen protocol |
| Independent coastal scenes | Measure domain generalization | Data collection and provenance burden | New verified imagery and expert labels; high | No | Performance reported by held-out site/season |

## Scope and provenance

This is an offline research analysis of official MARIDA validation data. It does not call the production upload API, register research imagery, alter source masks, change production settings, or modify weights.

## Post-freeze Stage 3 reproducibility check

After the validation threshold and calibration results were frozen, a separate regression run of the unchanged Stage 3 evaluator on the official test split reproduced the saved Stage 3 metrics exactly (359 scenes, 194,863 labeled pixels, and identical per-class, debris, confidence, and upstream/local comparison metrics). This check was not used to choose or modify any Stage 4 threshold or calibration result. The Stage 4 analysis above itself did not read test IDs, test imagery, or Stage 3 test metrics.
