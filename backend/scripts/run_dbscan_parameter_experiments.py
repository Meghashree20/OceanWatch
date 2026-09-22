"""Run the reproducible Phase 11 DBSCAN parameter sensitivity experiment."""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN


BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = BACKEND_DIR.parent
INPUT_PATH = BACKEND_DIR / "data" / "processed" / "ocean_water_clean.csv"
RESULT_PATH = BACKEND_DIR / "data" / "processed" / "dbscan_parameter_results.csv"
REPORT_PATH = REPO_DIR / "docs" / "DBSCAN_PARAMETER_EXPERIMENTS.md"
FIGURES_DIR = REPO_DIR / "docs" / "figures"
EPS_VALUES = [50, 100, 150, 200, 250, 300, 400]
MIN_SAMPLES_VALUES = [5, 10, 15, 20]
EARTH_RADIUS_KM = 6371.0


def load_coordinates() -> pd.DataFrame:
    frame = pd.read_csv(INPUT_PATH, low_memory=False)
    frame["latitude"] = pd.to_numeric(frame["Latitude (degree)"], errors="coerce")
    frame["longitude"] = pd.to_numeric(frame["Longitude (degree)"], errors="coerce")
    frame["measurement"] = pd.to_numeric(frame["Microplastics Measurement"], errors="coerce")
    frame = frame.dropna(subset=["latitude", "longitude", "measurement"])
    if frame.empty:
        raise ValueError("The cleaned dataset contains no valid geographic observations.")
    if not frame["latitude"].between(-90, 90).all() or not frame["longitude"].between(-180, 180).all():
        raise ValueError("The cleaned dataset contains invalid coordinates.")
    return frame.reset_index(drop=True)


def centroid_distances_km(coordinates_rad: np.ndarray, labels: np.ndarray) -> list[float]:
    distances = []
    for cluster_id in sorted(set(labels)):
        if cluster_id == -1:
            continue
        members = coordinates_rad[labels == cluster_id]
        centroid = members.mean(axis=0)
        lat_1 = members[:, 0]
        lon_1 = members[:, 1]
        lat_2, lon_2 = centroid
        haversine = 2 * np.arcsin(np.sqrt(
            np.sin((lat_1 - lat_2) / 2) ** 2
            + np.cos(lat_1) * np.cos(lat_2) * np.sin((lon_1 - lon_2) / 2) ** 2
        ))
        distances.extend((EARTH_RADIUS_KM * haversine).tolist())
    return distances


def run_experiment(frame: pd.DataFrame) -> pd.DataFrame:
    coordinates_rad = np.radians(frame[["latitude", "longitude"]].to_numpy())
    rows = []
    for eps_km in EPS_VALUES:
        for min_samples in MIN_SAMPLES_VALUES:
            labels = DBSCAN(
                eps=eps_km / EARTH_RADIUS_KM,
                min_samples=min_samples,
                algorithm="ball_tree",
                metric="haversine",
            ).fit_predict(coordinates_rad)
            cluster_sizes = pd.Series(labels[labels >= 0]).value_counts().sort_index()
            cluster_distances = centroid_distances_km(coordinates_rad, labels)
            cluster_count = len(cluster_sizes)
            noise_points = int((labels == -1).sum())
            rows.append({
                "eps_km": eps_km,
                "min_samples": min_samples,
                "number_of_clusters": cluster_count,
                "number_of_noise_points": noise_points,
                "noise_percentage": round(noise_points / len(labels) * 100, 4),
                "minimum_cluster_size": int(cluster_sizes.min()) if cluster_count else 0,
                "maximum_cluster_size": int(cluster_sizes.max()) if cluster_count else 0,
                "mean_cluster_size": round(float(cluster_sizes.mean()), 4) if cluster_count else 0.0,
                "median_cluster_size": round(float(cluster_sizes.median()), 4) if cluster_count else 0.0,
                "largest_cluster_percentage": round(float(cluster_sizes.max() / len(labels) * 100), 4) if cluster_count else 0.0,
                "mean_centroid_distance_km": round(float(np.mean(cluster_distances)), 4) if cluster_distances else None,
                "median_centroid_distance_km": round(float(np.median(cluster_distances)), 4) if cluster_distances else None,
            })
    return pd.DataFrame(rows)


def make_plots(results: pd.DataFrame) -> None:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    for value, filename, ylabel in [
        ("number_of_clusters", "dbscan_eps_vs_clusters.png", "Number of clusters"),
        ("noise_percentage", "dbscan_eps_vs_noise.png", "Noise percentage"),
    ]:
        figure, axis = plt.subplots(figsize=(9, 5))
        for min_samples, group in results.groupby("min_samples"):
            axis.plot(group["eps_km"], group[value], marker="o", label=f"min_samples={min_samples}")
        axis.set_xlabel("eps (km)")
        axis.set_ylabel(ylabel)
        axis.set_title(f"DBSCAN sensitivity: {ylabel.lower()}")
        axis.grid(alpha=0.3)
        axis.legend()
        figure.tight_layout()
        figure.savefig(FIGURES_DIR / filename, dpi=160)
        plt.close(figure)

    figure, axis = plt.subplots(figsize=(9, 5))
    for eps_km, group in results.groupby("eps_km"):
        axis.plot(group["min_samples"], group["number_of_clusters"], marker="o", label=f"eps={eps_km} km")
    axis.set_xlabel("min_samples")
    axis.set_ylabel("Number of clusters")
    axis.set_title("DBSCAN sensitivity: min_samples vs cluster count")
    axis.grid(alpha=0.3)
    axis.legend(ncol=2)
    figure.tight_layout()
    figure.savefig(FIGURES_DIR / "dbscan_min_samples_vs_clusters.png", dpi=160)
    plt.close(figure)


def select_configuration(results: pd.DataFrame) -> pd.Series:
    """Select a balanced empirical configuration, not a cluster-count maximum."""
    candidates = results[
        results["noise_percentage"].between(15, 35)
        & (results["minimum_cluster_size"] >= 10)
        & (results["largest_cluster_percentage"] < 25)
        & results["number_of_clusters"].between(40, 100)
    ].copy()
    if candidates.empty:
        candidates = results.copy()
    candidates["balance_score"] = (
        (1 - (candidates["noise_percentage"] - 25).abs() / 25).clip(lower=0)
        + (1 - (candidates["number_of_clusters"] - 60).abs() / 60).clip(lower=0)
        + (1 - candidates["largest_cluster_percentage"] / 25).clip(lower=0)
        - candidates["mean_centroid_distance_km"].fillna(candidates["mean_centroid_distance_km"].max()) / 10000
    )
    return candidates.sort_values(["balance_score", "eps_km", "min_samples"], ascending=[False, True, True]).iloc[0]


def markdown_table(results: pd.DataFrame) -> str:
    headers = list(results.columns)
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in results.itertuples(index=False, name=None):
        values = ["" if pd.isna(value) else str(value) for value in row]
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def write_report(results: pd.DataFrame, selected: pd.Series, input_rows: int) -> None:
    table = markdown_table(results)
    report = f"""# DBSCAN Parameter Experiments

Generated from `backend/data/processed/ocean_water_clean.csv` by
`backend/scripts/run_dbscan_parameter_experiments.py`.

## Method

- Input observations: **{input_rows}**
- Coordinate fields: `Latitude (degree)` and `Longitude (degree)`
- Distance: geographic Haversine distance on a sphere
- Earth radius used for conversion: **{EARTH_RADIUS_KM} km**
- Grid: eps values `{EPS_VALUES}` and min_samples values `{MIN_SAMPLES_VALUES}`
- Total configurations: **{len(results)}**

Compactness is measured as the mean and median great-circle distance from each
cluster member to that cluster's geographic centroid. It is a spatial quality
indicator, not a scientific validation metric.

## Results

{table}

## Visualizations

- [eps versus cluster count](figures/dbscan_eps_vs_clusters.png)
- [eps versus noise percentage](figures/dbscan_eps_vs_noise.png)
- [min_samples versus cluster count](figures/dbscan_min_samples_vs_clusters.png)

## Empirical selection

The selected configuration is **eps_km={int(selected['eps_km'])},
min_samples={int(selected['min_samples'])}**. It was selected based on empirical
parameter sensitivity analysis, considering noise percentage, non-trivial cluster
sizes, geographic compactness, avoidance of one dominant cluster, and avoidance of
near-total noise. It was not selected solely by maximizing or minimizing cluster
count, and it is not claimed to be scientifically optimal.

Observed selected-configuration values:

- Clusters: **{int(selected['number_of_clusters'])}**
- Noise points: **{int(selected['number_of_noise_points'])}**
- Noise percentage: **{selected['noise_percentage']}%**
- Minimum cluster size: **{int(selected['minimum_cluster_size'])}**
- Maximum cluster size: **{int(selected['maximum_cluster_size'])}**
- Mean cluster size: **{selected['mean_cluster_size']}**
- Median cluster size: **{selected['median_cluster_size']}**
- Largest cluster percentage: **{selected['largest_cluster_percentage']}%**
- Mean centroid distance: **{selected['mean_centroid_distance_km']} km**
- Median centroid distance: **{selected['median_centroid_distance_km']} km**

The selected values are stored in the configuration system as `DBSCAN_EPS_KM` and
`DBSCAN_MIN_SAMPLES`, with the current defaults set to the empirically selected
values. They can be overridden through environment variables.
"""
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")


def main() -> None:
    frame = load_coordinates()
    results = run_experiment(frame)
    selected = select_configuration(results)
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(RESULT_PATH, index=False)
    make_plots(results)
    write_report(results, selected, len(frame))
    print(f"Wrote {RESULT_PATH}")
    print(f"Wrote {REPORT_PATH}")
    print(f"Selected eps_km={int(selected['eps_km'])}, min_samples={int(selected['min_samples'])}")


if __name__ == "__main__":
    sys.path.insert(0, str(BACKEND_DIR))
    main()
