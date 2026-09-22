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
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

import pandas as pd

from app.db.mongodb import db_client
from app.ml.hotspot_model import DBSCANConfig, run_dbscan
from app.schemas.hotspot import HotspotStatsResponse
from app.core.config import settings
from app.core.dates import parse_date_range

logger = logging.getLogger(__name__)

HOTSPOT_COLLECTION = "hotspot_results"
RUN_COLLECTION = "hotspot_detection_runs"
OBSERVATION_COLLECTION = "pollution_observations"


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
    ) -> Dict[str, Any]:
        """
        1. Fetch observations from MongoDB (with optional filters).
        2. Run DBSCAN with Haversine distance.
        3. Persist cluster results to hotspot_results collection.
        4. Return summary stats.
        """
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

        df = pd.DataFrame(docs)
        if "sample_date" in df.columns:
            df["sample_date"] = pd.to_datetime(df["sample_date"], errors="coerce")

        config = DBSCANConfig(eps_km=eps_km, min_samples=min_samples)
        labelled_df, cluster_stats = run_dbscan(df, config)

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
            "total_clusters": n_clusters,
            "noise_points": n_noise,
            "total_observations_used": len(labelled_df),
            "severity_distribution": severity_dist,
            "filters": {
                "region": region,
                "start_date": start_date,
                "end_date": end_date,
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
