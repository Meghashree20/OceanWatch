"""Regression checks for the isolated Stage 4 validation analysis helpers."""

import sys
from pathlib import Path

import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from analyze_marida_stage4 import (  # noqa: E402
    binary_metrics,
    resolve_validation_dataset_root,
    threshold_predictions,
)


def test_threshold_strategies_remain_distinct_for_non_argmax_debris_score():
    argmax = np.array([1, 0, 2])
    max_confidence = np.array([0.45, 0.55, 0.60])
    debris_probability = np.array([0.40, 0.55, 0.35])

    strategy_a, strategy_b = threshold_predictions(argmax, max_confidence, debris_probability, 0.35)

    assert strategy_a.tolist() == [False, True, False]
    assert strategy_b.tolist() == [True, True, True]


def test_binary_debris_metrics_count_only_labeled_pixels():
    truth_debris = np.array([True, True, False, False])
    predicted_debris = np.array([True, False, True, False])

    result = binary_metrics(truth_debris, predicted_debris)

    assert result["support"] == 2
    assert result["predicted_debris_pixels_labeled"] == 2
    assert result["true_positives"] == 1
    assert result["false_positives"] == 1
    assert result["false_negatives"] == 1
    assert result["precision"] == 0.5
    assert result["recall"] == 0.5
    assert result["f1"] == 0.5
    assert result["iou"] == 1 / 3


def test_validation_root_resolution_needs_no_test_manifest(tmp_path):
    (tmp_path / "patches").mkdir()
    split_dir = tmp_path / "splits"
    split_dir.mkdir()
    (split_dir / "train_X.txt").write_text("train_roi\n", encoding="utf-8")
    (split_dir / "val_X.txt").write_text("val_roi\n", encoding="utf-8")

    assert resolve_validation_dataset_root(tmp_path) == tmp_path
    assert not (split_dir / "test_X.txt").exists()
