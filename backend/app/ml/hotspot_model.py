"""
OceanWatch — DBSCAN Hotspot Detection Model
============================================

Uses DBSCAN with Haversine distance to identify geographic clusters
of marine plastic pollution observations. Raw lat/lon coordinates are
converted to radians so that sklearn's haversine metric operates on
the correct unit (great-circle distance on a sphere).

DBSCAN Parameters:
    EPS_KM      — neighbourhood radius in kilometres (default: 200 km)
    MIN_SAMPLES — minimum points to form a dense cluster (default: 10)

Severity Thresholds (average_pollution in pieces/m³):
    LOW      — [0,       1.0)    — sparse, likely background level
    MEDIUM   — [1.0,    10.0)    — moderate concentration
    HIGH     — [10.0,  100.0)    — significant concentration
    CRITICAL — [100.0,   ∞  )    — extreme concentration

NOTE: These thresholds are configurable via DBSCANConfig.
      Clusters are labelled "Potential Pollution Hotspots" because the
      underlying data consists of sampled observations, not continuous
      spatial measurements.  No scientific ground-truth is claimed.
"""

import logging
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN

from app.core.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class DBSCANConfig:
    """
    Configurable parameters for DBSCAN hotspot detection.

    Attributes:
        eps_km:      Neighbourhood radius in kilometres.
                     Observations within this radius of each other are
                     considered neighbours.  Rule of thumb: start at 200 km
                     for ocean-scale clustering; reduce for coastal detail.
        min_samples: Minimum number of observations inside eps_km for a core
                     point.  Higher = fewer, denser clusters.
    """
    eps_km: float = settings.DBSCAN_EPS_KM
    min_samples: int = settings.DBSCAN_MIN_SAMPLES

    # Severity thresholds (avg_pollution in pieces/m³)
    # Keys are lower-bounds; the highest matched label wins.
    severity_thresholds: Dict[str, float] = field(default_factory=lambda: {
        "LOW":      0.0,
        "MEDIUM":   1.0,
        "HIGH":     10.0,
        "CRITICAL": 100.0,
    })


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

EARTH_RADIUS_KM = 6371.0


def _classify_severity(avg_pollution: float, thresholds: Dict[str, float]) -> str:
    """
    Assign a severity label based on the cluster's average pollution.

    Iterates through ascending threshold values and returns the highest
    label whose lower-bound is not exceeded.
    """
    label = "LOW"
    for lvl, bound in sorted(thresholds.items(), key=lambda x: x[1]):
        if avg_pollution >= bound:
            label = lvl
    return label


def _date_range(dates: pd.Series) -> Dict[str, Optional[str]]:
    """Return min/max date strings (ISO) from a Series of datetimes."""
    valid = dates.dropna()
    if valid.empty:
        return {"min": None, "max": None}
    return {
        "min": str(valid.min())[:10],
        "max": str(valid.max())[:10],
    }


# ---------------------------------------------------------------------------
# Core detection function
# ---------------------------------------------------------------------------

def run_dbscan(
    df: pd.DataFrame,
    config: DBSCANConfig,
) -> Tuple[pd.DataFrame, List[Dict]]:
    """
    Run DBSCAN on ocean-water observations using Haversine distance.

    Steps:
    1. Convert latitude/longitude to radians (required by sklearn's
       haversine metric which works on a unit sphere).
    2. eps = eps_km / EARTH_RADIUS_KM  (convert km → radians).
    3. Fit DBSCAN; assign cluster_id (-1 = noise).
    4. Compute per-cluster statistics.

    Args:
        df:     DataFrame containing columns:
                  latitude, longitude, measurement, sample_date,
                  region, ocean, unique_id
        config: DBSCANConfig instance.

    Returns:
        (labelled_df, cluster_stats_list)
        labelled_df     — original df with new 'cluster_id' column
        cluster_stats   — list of dicts, one per detected cluster
    """
    required_cols = {"latitude", "longitude", "measurement"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"Input DataFrame missing required columns: {missing}")

    df = df.copy()

    # Drop rows where lat/lon/measurement are NaN
    df = df.dropna(subset=["latitude", "longitude", "measurement"])

    if df.empty:
        logger.warning("No valid observations to cluster.")
        df["cluster_id"] = -1
        return df, []

    logger.info(
        f"Running DBSCAN on {len(df)} observations | "
        f"eps_km={config.eps_km} | min_samples={config.min_samples}"
    )

    # Convert degrees → radians for haversine metric
    coords_rad = np.radians(df[["latitude", "longitude"]].values)

    eps_rad = config.eps_km / EARTH_RADIUS_KM

    db = DBSCAN(
        eps=eps_rad,
        min_samples=config.min_samples,
        algorithm="ball_tree",
        metric="haversine",
    ).fit(coords_rad)

    df["cluster_id"] = db.labels_

    # Summary
    n_clusters = len(set(db.labels_)) - (1 if -1 in db.labels_ else 0)
    n_noise = int((db.labels_ == -1).sum())
    logger.info(f"DBSCAN complete: {n_clusters} clusters | {n_noise} noise points")

    # ---------------------------------------------------------------------------
    # Per-cluster statistics
    # ---------------------------------------------------------------------------
    cluster_stats: List[Dict] = []

    for cid in sorted(set(db.labels_)):
        if cid == -1:
            continue  # skip noise

        mask = df["cluster_id"] == cid
        sub = df[mask]

        avg_p = float(sub["measurement"].mean())
        severity = _classify_severity(avg_p, config.severity_thresholds)

        # Most common region / ocean in this cluster
        region = (
            sub["region"].dropna().mode().iloc[0]
            if "region" in sub.columns and not sub["region"].dropna().empty
            else None
        )
        ocean = (
            sub["ocean"].dropna().mode().iloc[0]
            if "ocean" in sub.columns and not sub["ocean"].dropna().empty
            else None
        )

        cluster_stats.append({
            "cluster_id": int(cid),
            "observation_count": int(len(sub)),
            "centroid": {
                "latitude": round(float(sub["latitude"].mean()), 6),
                "longitude": round(float(sub["longitude"].mean()), 6),
            },
            "centroid_latitude": round(float(sub["latitude"].mean()), 6),
            "centroid_longitude": round(float(sub["longitude"].mean()), 6),
            "average_pollution": round(avg_p, 4),
            "median_pollution": round(float(sub["measurement"].median()), 4),
            "maximum_pollution": round(float(sub["measurement"].max()), 4),
            "minimum_pollution": round(float(sub["measurement"].min()), 4),
            "pollution_std": round(float(sub["measurement"].std(ddof=0)), 4),
            "date_range": _date_range(sub.get("sample_date", pd.Series(dtype="object"))),
            "date_start": _date_range(sub.get("sample_date", pd.Series(dtype="object")))["min"],
            "date_end": _date_range(sub.get("sample_date", pd.Series(dtype="object")))["max"],
            "region": region,
            "dominant_region": region,
            "ocean": ocean,
            "severity": severity,
            "label": "Potential Pollution Hotspot",
        })

    return df, cluster_stats
