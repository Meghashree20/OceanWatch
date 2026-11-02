"""
OceanWatch — Hotspot Service
=============================

Orchestrates fetching observations from MongoDB, running DBSCAN via
hotspot_model.py, persisting results back to MongoDB, and providing
query helpers for the REST API.
"""

import logging
import hashlib
import json
import math
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Literal, Optional, Any

import pandas as pd

from app.db.mongodb import db_client
from app.ml.hotspot_model import DBSCANConfig, EARTH_RADIUS_KM, run_dbscan
from app.services.observation_service import ObservationService
from app.schemas.hotspot import HotspotStatsResponse
from app.core.config import settings
from app.core.dates import parse_date_range

logger = logging.getLogger(__name__)

HOTSPOT_COLLECTION = "hotspot_results"
RUN_COLLECTION = "hotspot_detection_runs"
OBSERVATION_COLLECTION = "pollution_observations"
HotspotMode = Literal["historical", "recent", "compare"]
DEFAULT_RECENT_WINDOW_DAYS = 90


def filter_recent_observations(
    observations: pd.DataFrame,
    window_days: int,
    reference_time: Optional[datetime] = None,
) -> pd.DataFrame:
    """Keep dated observations in the inclusive UTC interval ending now."""
    if window_days < 1:
        raise ValueError("window_days must be at least 1")
    if "sample_date" not in observations.columns:
        return observations.iloc[0:0].copy()

    reference = pd.Timestamp(reference_time or datetime.now(timezone.utc))
    if reference.tzinfo is None:
        reference = reference.tz_localize("UTC")
    else:
        reference = reference.tz_convert("UTC")
    dates = pd.to_datetime(observations["sample_date"], errors="coerce", utc=True)
    cutoff = reference - pd.Timedelta(days=window_days)
    return observations.loc[dates.ge(cutoff) & dates.le(reference)].copy()


def filter_historical_observations(
    observations: pd.DataFrame,
    window_days: int,
    reference_time: Optional[datetime] = None,
) -> pd.DataFrame:
    """Keep dated observations strictly before the recent UTC window."""
    if window_days < 1:
        raise ValueError("window_days must be at least 1")
    if "sample_date" not in observations.columns:
        return observations.iloc[0:0].copy()

    reference = pd.Timestamp(reference_time or datetime.now(timezone.utc))
    if reference.tzinfo is None:
        reference = reference.tz_localize("UTC")
    else:
        reference = reference.tz_convert("UTC")
    dates = pd.to_datetime(observations["sample_date"], errors="coerce", utc=True)
    cutoff = reference - pd.Timedelta(days=window_days)
    return observations.loc[dates.lt(cutoff) & dates.le(reference)].copy()


def classify_temporal_hotspots(
    historical_hotspots: List[Dict[str, Any]],
    recent_hotspots: List[Dict[str, Any]],
    eps_km: float,
) -> List[Dict[str, Any]]:
    """Merge cluster summaries by great-circle centroid proximity."""
    matches: Dict[int, List[tuple[Dict[str, Any], Dict[str, Any]]]] = {}
    unmatched_recent: List[Dict[str, Any]] = []

    for recent in recent_hotspots:
        recent_centroid = recent["centroid"]
        candidates = []
        for index, historical in enumerate(historical_hotspots):
            historical_centroid = historical["centroid"]
            lat1, lon1 = math.radians(recent_centroid["latitude"]), math.radians(recent_centroid["longitude"])
            lat2, lon2 = math.radians(historical_centroid["latitude"]), math.radians(historical_centroid["longitude"])
            delta_lat, delta_lon = lat2 - lat1, lon2 - lon1
            haversine = (
                math.sin(delta_lat / 2) ** 2
                + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2
            )
            distance_km = 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(min(1.0, haversine)))
            if distance_km <= eps_km:
                candidates.append((distance_km, index, historical))

        if candidates:
            _, historical_index, historical = min(candidates, key=lambda item: item[0])
            matches.setdefault(historical_index, []).append((recent, historical))
        else:
            unmatched_recent.append(recent)

    classified: List[Dict[str, Any]] = []
    matched_historical = set(matches)
    for recent_matches in matches.values():
        for recent, historical in recent_matches:
            hotspot = dict(recent)
            hotspot["temporal_classification"] = "persistent_emerging"
            hotspot["historical_observation_count"] = historical["observation_count"]
            hotspot["recent_observation_count"] = recent["observation_count"]
            classified.append(hotspot)

    for recent in unmatched_recent:
        hotspot = dict(recent)
        hotspot["temporal_classification"] = "emerging"
        hotspot["historical_observation_count"] = 0
        hotspot["recent_observation_count"] = recent["observation_count"]
        classified.append(hotspot)

    for index, historical in enumerate(historical_hotspots):
        if index not in matched_historical:
            hotspot = dict(historical)
            hotspot["temporal_classification"] = "persistent"
            hotspot["historical_observation_count"] = historical["observation_count"]
            hotspot["recent_observation_count"] = 0
            classified.append(hotspot)

    for cluster_id, hotspot in enumerate(classified):
        hotspot["cluster_id"] = cluster_id
    return classified


class HotspotService:

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------

    @staticmethod
    async def detect_hotspots(
        eps_km: float = settings.DBSCAN_EPS_KM,
        min_samples: int = settings.DBSCAN_MIN_SAMPLES,
        region: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        mode: HotspotMode = "historical",
        recent_window_days: int = DEFAULT_RECENT_WINDOW_DAYS,
    ) -> Dict[str, Any]:
        """
        Run historical, recent, or comparison detection on NOAA observations.

        Keep the OceanWatch Haversine model: unlike the reference project's
        StandardScaler over coordinates and measurements, its eps is a real
        geographic radius in kilometers.
        """
        if mode not in ("historical", "recent", "compare"):
            raise ValueError(f"Unsupported hotspot mode: {mode}")
        if recent_window_days < 1:
            raise ValueError("recent_window_days must be at least 1")

        obs_col = db_client.db[OBSERVATION_COLLECTION]

        # Build query filter
        query: Dict = {}
        if region:
            query["region"] = region
        try:
            start_bound, end_bound = parse_date_range(start_date, end_date)
        except ValueError:
            raise
        if start_bound or end_bound:
            query["sample_date"] = {}
            if start_bound:
                query["sample_date"]["$gte"] = start_bound
            if end_bound:
                query["sample_date"]["$lte"] = end_bound

        logger.info(f"Fetching observations for DBSCAN | filter={query}")
        cursor = obs_col.find(query, {
            "_id": 0,
            "unique_id": 1, "latitude": 1, "longitude": 1,
            "measurement": 1, "sample_date": 1,
            "region": 1, "ocean": 1,
        })
        docs = await cursor.to_list(length=None)

        if not docs:
            return {"status": "no_data", "message": "No observations match the filters."}

        normalized = [
            ObservationService.from_noaa(doc)
            for doc in docs
            if all(doc.get(key) is not None for key in ("unique_id", "latitude", "longitude", "measurement"))
        ]
        df = pd.DataFrame([
            {
                "unique_id": observation.source_id,
                "latitude": observation.latitude,
                "longitude": observation.longitude,
                "measurement": observation.value,
                "sample_date": observation.observed_at,
                "region": observation.region,
                "ocean": observation.ocean,
            }
            for observation in normalized
        ], columns=[
            "unique_id", "latitude", "longitude", "measurement",
            "sample_date", "region", "ocean",
        ])
        reference_time = datetime.now(timezone.utc)
        recent_df = filter_recent_observations(df, recent_window_days, reference_time)
        comparison_history_df = (
            filter_historical_observations(df, recent_window_days, reference_time)
            if mode == "compare"
            else df
        )

        config = DBSCANConfig(eps_km=eps_km, min_samples=min_samples)
        historical_labelled: Optional[pd.DataFrame] = None
        recent_labelled: Optional[pd.DataFrame] = None
        historical_stats: List[Dict[str, Any]] = []
        recent_stats: List[Dict[str, Any]] = []

        if mode in ("historical", "compare"):
            historical_labelled, historical_stats = run_dbscan(comparison_history_df, config)
        if mode in ("recent", "compare"):
            recent_labelled, recent_stats = run_dbscan(recent_df, config)

        if mode == "historical":
            assert historical_labelled is not None
            labelled_df, cluster_stats = historical_labelled, historical_stats
        elif mode == "recent":
            assert recent_labelled is not None
            labelled_df, cluster_stats = recent_labelled, recent_stats
        else:
            assert historical_labelled is not None and recent_labelled is not None
            labelled_df = historical_labelled
            cluster_stats = classify_temporal_hotspots(historical_stats, recent_stats, eps_km)

        created_at = datetime.now(timezone.utc)
        run_id = uuid.uuid4().hex
        dataset_payload = [
            {
                key: str(doc.get(key))
                for key in ("unique_id", "sample_date", "latitude", "longitude", "measurement")
            }
            for doc in sorted(docs, key=lambda item: str(item.get("unique_id", "")))
        ]
        dataset_hash = hashlib.sha256(
            json.dumps(dataset_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

        # Preserve every execution as a separate run and result set.
        hs_col = db_client.db[HOTSPOT_COLLECTION]

        if cluster_stats:
            for cs in cluster_stats:
                cs["hotspot_id"] = f"{run_id}:{cs['cluster_id']}"
                cs["detection_run_id"] = run_id
                cs["created_at"] = created_at
                cs["dataset_hash"] = dataset_hash
                cs["eps_km"] = eps_km
                cs["min_samples"] = min_samples
                cs["analysis_mode"] = mode
            await hs_col.insert_many(cluster_stats)

        # Noise stats
        n_clusters = len(cluster_stats)
        n_noise = int((labelled_df["cluster_id"] == -1).sum())

        severity_dist: Dict[str, int] = {}
        for cs in cluster_stats:
            sev = cs["severity"]
            severity_dist[sev] = severity_dist.get(sev, 0) + 1

        run_doc = {
            "run_id": run_id,
            "created_at": created_at,
            "eps_km": eps_km,
            "min_samples": min_samples,
            "dataset_hash": dataset_hash,
            "mode": mode,
            "recent_window_days": recent_window_days,
            "recent_cutoff": reference_time - timedelta(days=recent_window_days),
            "total_clusters": n_clusters,
            "noise_points": n_noise,
            "total_observations_used": len(labelled_df),
            "severity_distribution": severity_dist,
            "filters": {
                "region": region,
                "start_date": start_date,
                "end_date": end_date,
                "mode": mode,
            },
            "status": "success",
        }
        await db_client.db[RUN_COLLECTION].insert_one(run_doc)

        return {
            "status": "success",
            "detection_run_id": run_id,
            "created_at": created_at,
            "dataset_hash": dataset_hash,
            "total_clusters": n_clusters,
            "noise_points": n_noise,
            "total_observations_used": len(labelled_df),
            "eps_km": eps_km,
            "min_samples": min_samples,
            "severity_distribution": severity_dist,
            "mode": mode,
            "recent_window_days": recent_window_days,
            "historical_observations_used": (
                len(historical_labelled) if historical_labelled is not None else None
            ),
            "recent_observations_used": (
                len(recent_labelled) if recent_labelled is not None else None
            ),
        }

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    @staticmethod
    async def get_hotspots(
        skip: int = 0,
        limit: int = 100,
        severity: Optional[str] = None,
        ocean: Optional[str] = None,
        region: Optional[str] = None,
        detection_run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        hs_col = db_client.db[HOTSPOT_COLLECTION]
        query: Dict = {}
        if severity:
            query["severity"] = severity.upper()
        if ocean:
            query["ocean"] = ocean
        if region:
            query["region"] = region
        if detection_run_id:
            query["detection_run_id"] = detection_run_id

        cursor = hs_col.find(query, {"_id": 0}).skip(skip).limit(limit)
        results = await cursor.to_list(length=limit)
        total = await hs_col.count_documents(query)
        return {"data": results, "total": total, "skip": skip, "limit": limit}

    @staticmethod
    async def get_hotspot_by_id(cluster_id: int) -> Optional[Dict]:
        hs_col = db_client.db[HOTSPOT_COLLECTION]
        latest_run = await db_client.db[RUN_COLLECTION].find_one({}, {"_id": 0, "run_id": 1}, sort=[("created_at", -1)])
        query = {"cluster_id": cluster_id}
        if latest_run:
            query["detection_run_id"] = latest_run["run_id"]
        doc = await hs_col.find_one(query, {"_id": 0})
        return doc

    @staticmethod
    async def get_hotspot_by_run_and_id(run_id: str, cluster_id: int) -> Optional[Dict]:
        return await db_client.db[HOTSPOT_COLLECTION].find_one(
            {"detection_run_id": run_id, "cluster_id": cluster_id}, {"_id": 0}
        )

    @staticmethod
    async def get_runs(skip: int = 0, limit: int = 100) -> Dict[str, Any]:
        collection = db_client.db[RUN_COLLECTION]
        cursor = collection.find({}, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit)
        runs = await cursor.to_list(length=limit)
        total = await collection.count_documents({})
        return {"data": runs, "total": total, "skip": skip, "limit": limit}

    @staticmethod
    async def get_run(run_id: str) -> Optional[Dict[str, Any]]:
        return await db_client.db[RUN_COLLECTION].find_one({"run_id": run_id}, {"_id": 0})

    @staticmethod
    async def get_stats() -> Dict[str, Any]:
        hs_col = db_client.db[HOTSPOT_COLLECTION]
        total = await hs_col.count_documents({})

        # Severity distribution across all stored clusters
        pipeline = [{"$group": {"_id": "$severity", "count": {"$sum": 1}}}]
        cursor = hs_col.aggregate(pipeline)
        sev_docs = await cursor.to_list(length=None)
        severity_dist = {d["_id"]: d["count"] for d in sev_docs}

        # Total observations across all clusters
        pipeline2 = [{"$group": {"_id": None, "total_obs": {"$sum": "$observation_count"}}}]
        cursor2 = hs_col.aggregate(pipeline2)
        obs_docs = await cursor2.to_list(length=1)
        total_obs = obs_docs[0]["total_obs"] if obs_docs else 0

        # Latest run params
        latest = await db_client.db[RUN_COLLECTION].find_one(
            {}, {"_id": 0, "eps_km": 1, "min_samples": 1}, sort=[("created_at", -1)]
        )

        return {
            "total_clusters": total,
            "total_observations_in_clusters": total_obs,
            "severity_distribution": severity_dist,
            "last_run_eps_km": latest["eps_km"] if latest else None,
            "last_run_min_samples": latest["min_samples"] if latest else None,
        }
