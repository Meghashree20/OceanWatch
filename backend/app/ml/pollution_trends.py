"""Measured, equal-window spatial pollution trend analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import math
from typing import Any, Dict, Iterable, Optional

import pandas as pd

from app.core.config import settings


RISK_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}


@dataclass(frozen=True)
class PollutionTrendConfig:
    window_days: int = settings.POLLUTION_TREND_WINDOW_DAYS
    min_observations: int = settings.POLLUTION_TREND_MIN_OBSERVATIONS
    min_relative_change: float = settings.POLLUTION_TREND_MIN_RELATIVE_CHANGE
    cell_size_degrees: float = settings.POLLUTION_TREND_CELL_SIZE_DEGREES
    risk_thresholds: Dict[str, float] = field(default_factory=lambda: {
        "MEDIUM": settings.POLLUTION_RISK_MEDIUM_THRESHOLD,
        "HIGH": settings.POLLUTION_RISK_HIGH_THRESHOLD,
        "CRITICAL": settings.POLLUTION_RISK_CRITICAL_THRESHOLD,
    })

    def validate(self) -> None:
        if self.window_days < 1 or self.min_observations < 1 or self.cell_size_degrees <= 0:
            raise ValueError("Trend windows, minimum observations, and cell size must be positive.")
        if self.min_relative_change < 0:
            raise ValueError("Minimum relative change must be non-negative.")
        thresholds = self.risk_thresholds
        if (
            set(thresholds) != {"MEDIUM", "HIGH", "CRITICAL"}
            or any(not math.isfinite(value) or value < 0 for value in thresholds.values())
            or not thresholds["MEDIUM"] < thresholds["HIGH"] < thresholds["CRITICAL"]
        ):
            raise ValueError("Risk thresholds must be finite and satisfy MEDIUM < HIGH < CRITICAL.")


def _risk_level(value: float, thresholds: Dict[str, float]) -> str:
    if value >= thresholds["CRITICAL"]:
        return "CRITICAL"
    if value >= thresholds["HIGH"]:
        return "HIGH"
    if value >= thresholds["MEDIUM"]:
        return "MEDIUM"
    return "LOW"


def _freshness(latest: Optional[pd.Timestamp]) -> Dict[str, Any]:
    if latest is None:
        return {"status": "unavailable", "age_days": None}
    age_days = max(0, int((pd.Timestamp.now(tz="UTC") - latest).total_seconds() // 86400))
    return {
        "status": (
            "fresh" if age_days <= min(30, settings.POLLUTION_DATA_FRESHNESS_MAX_DAYS)
            else "aging" if age_days <= settings.POLLUTION_DATA_FRESHNESS_MAX_DAYS
            else "stale"
        ),
        "age_days": age_days,
    }


def _period_cells(frame: pd.DataFrame, config: PollutionTrendConfig) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    size = config.cell_size_degrees
    frame = frame.copy()
    frame["cell_latitude"] = (
        (frame["latitude"] / size).apply(math.floor) * size + size / 2
    ).clip(-90 + size / 2, 90 - size / 2)
    frame["cell_longitude"] = (
        (frame["longitude"] / size).apply(math.floor) * size + size / 2
    ).clip(-180 + size / 2, 180 - size / 2)
    frame["site_latitude"] = frame["latitude"].round(4)
    frame["site_longitude"] = frame["longitude"].round(4)
    site_means = (
        frame.groupby(
            ["cell_latitude", "cell_longitude", "site_latitude", "site_longitude"],
            as_index=False,
        )
        .agg(site_mean=("measurement", "mean"))
    )
    balanced = (
        site_means.groupby(["cell_latitude", "cell_longitude"], as_index=False)
        .agg(
            mean=("site_mean", "mean"),
            site_count=("site_mean", "size"),
        )
    )
    raw_counts = (
        frame.groupby(["cell_latitude", "cell_longitude"], as_index=False)
        .agg(
            observation_count=("measurement", "size"),
            latest_observation=("sample_date", "max"),
            earliest_observation=("sample_date", "min"),
        )
    )
    return balanced.merge(raw_counts, on=["cell_latitude", "cell_longitude"])


def analyze_pollution_trends(
    records: Iterable[Dict[str, Any]],
    config: Optional[PollutionTrendConfig] = None,
    reference_time: Optional[datetime | str] = None,
) -> Dict[str, Any]:
    """Compare two adjacent equal-length windows without imputing absent data."""
    config = config or PollutionTrendConfig()
    config.validate()
    frame = pd.DataFrame(list(records))
    if frame.empty:
        return {
            "status": "insufficient_data",
            "source": "observed NOAA microplastic measurements",
            "unit": "pieces/m3",
            "windows": None,
            "latest_observation": None,
            "data_freshness": _freshness(None),
            "coverage": {"valid_observations": 0, "excluded_observations": 0},
            "trends": [],
        }
    required = {"sample_date", "latitude", "longitude", "measurement"}
    if required - set(frame.columns):
        raise ValueError(f"Trend data missing required columns: {sorted(required - set(frame.columns))}")

    frame["sample_date"] = pd.to_datetime(frame["sample_date"], errors="coerce", utc=True)
    for column in ("latitude", "longitude", "measurement"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["unit"] = frame.get("unit", pd.Series("pieces/m3", index=frame.index)).fillna("").astype(str).str.strip().str.lower()
    valid = (
        frame["sample_date"].notna()
        & frame["latitude"].between(-90, 90)
        & frame["longitude"].between(-180, 180)
        & frame["measurement"].map(lambda value: pd.notna(value) and math.isfinite(float(value)) and float(value) >= 0)
        & frame["unit"].eq("pieces/m3")
    )
    excluded_count = int((~valid).sum())
    frame = frame.loc[valid].copy()
    if frame.empty:
        return {
            "status": "insufficient_data",
            "source": "observed NOAA microplastic measurements",
            "unit": "pieces/m3",
            "windows": None,
            "latest_observation": None,
            "data_freshness": _freshness(None),
            "coverage": {"valid_observations": 0, "excluded_observations": excluded_count},
            "trends": [],
        }

    reference = pd.Timestamp(reference_time) if reference_time is not None else pd.Timestamp.now(tz="UTC")
    reference = reference.tz_localize("UTC") if reference.tzinfo is None else reference.tz_convert("UTC")
    future_rows = frame["sample_date"].gt(reference)
    excluded_count += int(future_rows.sum())
    frame = frame.loc[~future_rows].copy()
    if frame.empty:
        return {
            "status": "insufficient_data",
            "source": "observed NOAA microplastic measurements",
            "unit": "pieces/m3",
            "windows": None,
            "latest_observation": None,
            "data_freshness": _freshness(None),
            "coverage": {"valid_observations": 0, "excluded_observations": excluded_count},
            "trends": [],
        }
    latest = frame["sample_date"].max()
    recent_start = latest - pd.Timedelta(days=config.window_days)
    previous_start = recent_start - pd.Timedelta(days=config.window_days)
    recent_frame = frame.loc[frame["sample_date"].gt(recent_start) & frame["sample_date"].le(latest)]
    previous_frame = frame.loc[frame["sample_date"].gt(previous_start) & frame["sample_date"].le(recent_start)]
    recent = _period_cells(recent_frame, config)
    previous = _period_cells(previous_frame, config)
    if recent.empty:
        return {
            "status": "insufficient_data",
            "source": "observed NOAA microplastic measurements",
            "unit": "pieces/m3",
            "windows": {
                "previous": {"start": previous_start.isoformat(), "end": recent_start.isoformat()},
                "recent": {"start": recent_start.isoformat(), "end": latest.isoformat()},
                "days_per_window": config.window_days,
            },
            "latest_observation": latest.isoformat(),
            "data_freshness": _freshness(latest),
            "coverage": {
                "valid_observations": int(len(frame)),
                "excluded_observations": excluded_count,
                "recent_observations": int(len(recent_frame)),
                "previous_observations": int(len(previous_frame)),
            },
            "trends": [],
        }

    previous_by_cell = {
        (row.cell_latitude, row.cell_longitude): row
        for row in previous.itertuples()
        if row.observation_count >= config.min_observations
    } if not previous.empty else {}
    recent_rows = [
        row for row in recent.itertuples()
        if row.observation_count >= config.min_observations
    ]
    previous_high_cells = {
        (row.cell_latitude, row.cell_longitude)
        for row in previous.itertuples()
        if row.observation_count >= config.min_observations
        and _risk_level(float(row.mean), config.risk_thresholds) in {"HIGH", "CRITICAL"}
    } if not previous.empty else set()

    results = []
    for row in recent_rows:
        key = (row.cell_latitude, row.cell_longitude)
        current_mean = float(row.mean)
        current_risk = _risk_level(current_mean, config.risk_thresholds)
        baseline = previous_by_cell.get(key)
        previous_mean = float(baseline.mean) if baseline is not None else None
        previous_risk = _risk_level(previous_mean, config.risk_thresholds) if previous_mean is not None else None
        absolute_change = current_mean - previous_mean if previous_mean is not None else None
        relative_change = (
            absolute_change / previous_mean
            if absolute_change is not None and previous_mean > 0
            else None
        )
        adjacent_previous_high = any(
            (row.cell_latitude + dy * config.cell_size_degrees, row.cell_longitude + dx * config.cell_size_degrees)
            in previous_high_cells
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1))
        )
        change_types = []
        if baseline is None:
            change_types.append("no_comparable_baseline")
        else:
            if current_risk in {"HIGH", "CRITICAL"} and previous_risk in {"LOW", "MEDIUM"}:
                change_types.append("newly_high_risk")
            elif current_risk in {"HIGH", "CRITICAL"} and previous_risk in {"HIGH", "CRITICAL"}:
                change_types.append("persistent_hotspot")
            if (
                relative_change is not None
                and relative_change >= config.min_relative_change
            ):
                change_types.append("increasing_pollution")
            elif (
                previous_mean == 0
                and current_mean >= config.risk_thresholds["MEDIUM"]
            ):
                change_types.append("increasing_pollution")
            elif relative_change is not None and relative_change <= -config.min_relative_change:
                change_types.append("decreasing_pollution")
            if (
                current_risk in {"HIGH", "CRITICAL"}
                and previous_risk in {"LOW", "MEDIUM"}
                and adjacent_previous_high
            ):
                change_types.append("expanding_hotspot")

        quality = (
            "high" if row.observation_count >= 10 and row.site_count >= 3
            else "moderate" if row.site_count >= 2
            else "low"
        )
        results.append({
            "location": {
                "latitude": round(float(row.cell_latitude), 6),
                "longitude": round(float(row.cell_longitude), 6),
                "cell_size_degrees": config.cell_size_degrees,
            },
            "risk_level": current_risk,
            "trend_direction": (
                "increasing" if "increasing_pollution" in change_types or "newly_high_risk" in change_types
                else "decreasing" if "decreasing_pollution" in change_types
                else "stable" if baseline is not None
                else "unknown"
            ),
            "change_types": change_types,
            "comparison": {
                "recent_mean_pieces_m3": round(current_mean, 6),
                "previous_mean_pieces_m3": round(previous_mean, 6) if previous_mean is not None else None,
                "absolute_change_pieces_m3": round(absolute_change, 6) if absolute_change is not None else None,
                "relative_change": round(relative_change, 6) if relative_change is not None else None,
                "previous_risk_level": previous_risk,
            },
            "evidence": {
                "recent_observation_count": int(row.observation_count),
                "recent_sampling_site_count": int(row.site_count),
                "previous_observation_count": int(baseline.observation_count) if baseline is not None else None,
                "previous_sampling_site_count": int(baseline.site_count) if baseline is not None else None,
                "recent_period": {"start": recent_start.isoformat(), "end": latest.isoformat()},
                "previous_period": {"start": previous_start.isoformat(), "end": recent_start.isoformat()},
                "frequency_adjustment": "mean of per-site means; repeat observations at a site do not receive extra weight",
                "data_quality": quality,
                "baseline_available": baseline is not None,
                "adjacent_previous_high_risk_cell": adjacent_previous_high,
            },
            "source": "observed NOAA microplastic measurements",
        })

    results.sort(
        key=lambda item: (
            RISK_ORDER[item["risk_level"]],
            item["comparison"]["absolute_change_pieces_m3"] or 0,
            item["evidence"]["recent_observation_count"],
        ),
        reverse=True,
    )
    return {
        "status": "ready" if results else "insufficient_data",
        "source": "observed NOAA microplastic measurements",
        "unit": "pieces/m3",
        "thresholds": {
            "LOW": f"< {config.risk_thresholds['MEDIUM']}",
            "MEDIUM": f">= {config.risk_thresholds['MEDIUM']} and < {config.risk_thresholds['HIGH']}",
            "HIGH": f">= {config.risk_thresholds['HIGH']} and < {config.risk_thresholds['CRITICAL']}",
            "CRITICAL": f">= {config.risk_thresholds['CRITICAL']}",
        },
        "windows": {
            "previous": {"start": previous_start.isoformat(), "end": recent_start.isoformat()},
            "recent": {"start": recent_start.isoformat(), "end": latest.isoformat()},
            "days_per_window": config.window_days,
        },
        "latest_observation": latest.isoformat(),
        "data_freshness": _freshness(latest),
        "coverage": {
            "valid_observations": int(len(frame)),
            "excluded_observations": excluded_count,
            "recent_observations": int(len(recent_frame)),
            "previous_observations": int(len(previous_frame)),
            "recent_comparable_cells": len(results),
        },
        "trends": results,
    }
