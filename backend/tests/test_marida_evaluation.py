"""Unit checks for the reproducible evaluator, not model accuracy results."""

import sys
from pathlib import Path

import numpy as np
import torch

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from evaluate_marida import (  # noqa: E402
    EXPECTED_MODEL_SHA256,
    MODEL_PATH,
    UpstreamUNet,
    class_metrics,
    map_labels,
    sha256_file,
    summarize_scores,
)
from app.ml.satellite.unet import UNet  # noqa: E402


def test_official_source_labels_match_upstream_eleven_class_aggregation():
    source = np.array([[0, 1, 11, 12, 13, 14, 15]], dtype=np.uint8)
    mapped, valid = map_labels(source)

    assert mapped.tolist() == [[-1, 0, 10, 6, 6, 6, 6]]
    assert valid.tolist() == [[False, True, True, True, True, True, True]]


def test_absent_test_class_metrics_are_unavailable():
    matrix = np.zeros((11, 11), dtype=np.int64)
    matrix[6, 6] = 9
    matrix[6, 0] = 1
    rows, summary = class_metrics(matrix)

    assert rows[0]["support"] == 0
    assert rows[0]["false_positives"] == 1
    assert rows[0]["precision"] is None
    assert rows[0]["recall"] is None
    assert rows[0]["f1"] is None
    assert rows[0]["iou"] is None
    assert rows[0]["status"] == "unavailable_no_labeled_test_pixels"
    assert summary["labeled_pixels"] == 10


def test_confidence_summary_handles_empty_subsets_without_fake_scores():
    summary = summarize_scores(np.array([], dtype=np.float32))

    assert summary == {"count": 0, "mean": None, "std": None, "percentiles": {}}


def test_upstream_and_local_models_load_same_checkpoint_and_match_256_logits():
    assert sha256_file(MODEL_PATH) == EXPECTED_MODEL_SHA256
    checkpoint = torch.load(MODEL_PATH, map_location="cpu", weights_only=True)
    upstream = UpstreamUNet().eval()
    local = UNet().eval()
    upstream.load_state_dict(checkpoint, strict=True)
    local.load_state_dict(checkpoint, strict=True)
    image = torch.linspace(0, 1, 11 * 256 * 256, dtype=torch.float32).reshape(1, 11, 256, 256)

    with torch.inference_mode():
        upstream_logits = upstream(image)
        local_logits = local(image)

    assert torch.equal(upstream_logits, local_logits)
    assert torch.equal(upstream_logits.argmax(1), local_logits.argmax(1))
