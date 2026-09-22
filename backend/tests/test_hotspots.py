"""
Tests for DBSCAN hotspot detection logic.
"""
import pytest
import pandas as pd
import numpy as np
from app.ml.hotspot_model import DBSCANConfig, run_dbscan, _classify_severity


# ---------------------------------------------------------------------------
# Severity classification
# ---------------------------------------------------------------------------

def test_severity_low():
    thresholds = {"LOW": 0.0, "MEDIUM": 1.0, "HIGH": 10.0, "CRITICAL": 100.0}
    assert _classify_severity(0.5, thresholds) == "LOW"

def test_severity_medium():
    thresholds = {"LOW": 0.0, "MEDIUM": 1.0, "HIGH": 10.0, "CRITICAL": 100.0}
    assert _classify_severity(5.0, thresholds) == "MEDIUM"

def test_severity_high():
    thresholds = {"LOW": 0.0, "MEDIUM": 1.0, "HIGH": 10.0, "CRITICAL": 100.0}
    assert _classify_severity(50.0, thresholds) == "HIGH"

def test_severity_critical():
    thresholds = {"LOW": 0.0, "MEDIUM": 1.0, "HIGH": 10.0, "CRITICAL": 100.0}
    assert _classify_severity(500.0, thresholds) == "CRITICAL"


# ---------------------------------------------------------------------------
# DBSCAN model
# ---------------------------------------------------------------------------

def _make_tight_cluster_df():
    """Create two tight, well-separated geographic clusters and a noise point."""
    cluster1 = pd.DataFrame({
        "latitude":    [10.0, 10.1, 10.2, 10.0, 10.1] * 3,
        "longitude":   [20.0, 20.1, 20.0, 20.2, 20.1] * 3,
        "measurement": [1.0,  1.5,  2.0,  1.2,  1.8]  * 3,
        "region":      ["Asia"] * 15,
        "ocean":       ["Indian Ocean"] * 15,
        "unique_id":   [f"C1-{i}" for i in range(15)],
    })
    cluster2 = pd.DataFrame({
        "latitude":    [50.0, 50.1, 50.2, 50.0, 50.1] * 3,
        "longitude":   [90.0, 90.1, 90.0, 90.2, 90.1] * 3,
        "measurement": [200.0, 250.0, 300.0, 220.0, 180.0] * 3,
        "region":      ["North Pacific"] * 15,
        "ocean":       ["Pacific Ocean"] * 15,
        "unique_id":   [f"C2-{i}" for i in range(15)],
    })
    noise = pd.DataFrame({
        "latitude":    [-80.0],
        "longitude":   [-160.0],
        "measurement": [0.01],
        "region":      [None],
        "ocean":       [None],
        "unique_id":   ["NOISE-1"],
    })
    return pd.concat([cluster1, cluster2, noise], ignore_index=True)


def test_dbscan_finds_two_clusters():
    df = _make_tight_cluster_df()
    config = DBSCANConfig(eps_km=50.0, min_samples=5)
    labelled, stats = run_dbscan(df, config)
    assert len(stats) == 2, f"Expected 2 clusters, got {len(stats)}"


def test_dbscan_noise_point_is_minus_one():
    df = _make_tight_cluster_df()
    config = DBSCANConfig(eps_km=50.0, min_samples=5)
    labelled, _ = run_dbscan(df, config)
    noise_rows = labelled[labelled["unique_id"] == "NOISE-1"]
    assert noise_rows.iloc[0]["cluster_id"] == -1


def test_dbscan_cluster_severity_critical():
    """Cluster 2 has avg pollution ~230 → CRITICAL."""
    df = _make_tight_cluster_df()
    config = DBSCANConfig(eps_km=50.0, min_samples=5)
    _, stats = run_dbscan(df, config)
    sevs = {s["severity"] for s in stats}
    assert "CRITICAL" in sevs


def test_dbscan_missing_rows_are_dropped():
    df = pd.DataFrame({
        "latitude":    [10.0, None, 10.1],
        "longitude":   [20.0, 20.0, None],
        "measurement": [1.0,  2.0,  3.0],
    })
    config = DBSCANConfig(eps_km=50.0, min_samples=1)
    labelled, _ = run_dbscan(df, config)
    # The 2 rows with NaN lat/lon are dropped before clustering
    assert len(labelled) == 1


def test_dbscan_empty_df_returns_empty():
    df = pd.DataFrame(columns=["latitude", "longitude", "measurement"])
    config = DBSCANConfig(eps_km=200.0, min_samples=10)
    labelled, stats = run_dbscan(df, config)
    assert len(stats) == 0
    assert "cluster_id" in labelled.columns


def test_dbscan_label_is_potential_hotspot():
    df = _make_tight_cluster_df()
    config = DBSCANConfig(eps_km=50.0, min_samples=5)
    _, stats = run_dbscan(df, config)
    for s in stats:
        assert s["label"] == "Potential Pollution Hotspot"


def test_dbscan_provides_required_hotspot_statistics():
    _, stats = run_dbscan(_make_tight_cluster_df(), DBSCANConfig(eps_km=50.0, min_samples=5))
    required = {
        "cluster_id", "observation_count", "centroid_latitude", "centroid_longitude",
        "average_pollution", "median_pollution", "maximum_pollution", "minimum_pollution",
        "pollution_std", "date_start", "date_end", "dominant_region", "severity",
    }
    assert required.issubset(stats[0])
    assert stats[0]["median_pollution"] is not None
