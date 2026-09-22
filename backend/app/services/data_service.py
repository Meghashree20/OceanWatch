import pandas as pd
import math
from typing import Dict, Any, List, Optional
from datetime import datetime
from pymongo import UpdateOne
from app.db.mongodb import db_client
from app.schemas.pollution import PaginatedResponse
from app.core.logging_config import logger
from app.core.dates import parse_date_bound, parse_date_range

class DataService:
    @staticmethod
    def _clean_nan(val):
        if pd.isna(val) or (isinstance(val, float) and math.isnan(val)):
            return None
        return val

    @staticmethod
    async def import_data(csv_path: str) -> Dict[str, Any]:
        """
        Reads the cleaned CSV and bulk upserts into MongoDB.
        """
        logger.info(f"Importing data from {csv_path}...")
        try:
            df = pd.read_csv(csv_path, low_memory=False)
        except Exception as e:
            logger.error(f"Failed to read CSV: {e}")
            raise ValueError(f"Failed to read data file: {e}")

        required_columns = {
            "Unique ID", "Sample Date", "Latitude (degree)",
            "Longitude (degree)", "Microplastics Measurement", "Unit",
        }
        missing_columns = required_columns - set(df.columns)
        if missing_columns:
            raise ValueError(f"CSV is missing required columns: {sorted(missing_columns)}")
        numeric_columns = ["Latitude (degree)", "Longitude (degree)", "Microplastics Measurement"]
        for column in numeric_columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")
        parsed_dates = pd.to_datetime(df["Sample Date"], errors="coerce")
        invalid_rows = (
            df["Unique ID"].isna()
            | parsed_dates.isna()
            | df["Latitude (degree)"].isna()
            | df["Longitude (degree)"].isna()
            | df["Microplastics Measurement"].isna()
            | ~df["Latitude (degree)"].between(-90, 90)
            | ~df["Longitude (degree)"].between(-180, 180)
        )
        if invalid_rows.any():
            raise ValueError(f"CSV contains {int(invalid_rows.sum())} invalid observation rows")

        collection = db_client.db["pollution_observations"]
        
        operations = []
        for _, row in df.iterrows():
            # Convert date
            sample_date = None
            if pd.notnull(row.get("Sample Date")):
                try:
                    sample_date = parse_date_bound(str(row["Sample Date"]))
                except:
                    pass
            
            # Map fields
            doc = {
                "unique_id": str(row.get("Unique ID")),
                "sample_date": sample_date,
                "latitude": float(row.get("Latitude (degree)")),
                "longitude": float(row.get("Longitude (degree)")),
                "measurement": float(row.get("Microplastics Measurement")),
                "unit": str(row.get("Unit")),
                "concentration_class": DataService._clean_nan(row.get("Concentration Class")),
                "ocean": DataService._clean_nan(row.get("Ocean")),
                "region": DataService._clean_nan(row.get("Region")),
                "subregion": DataService._clean_nan(row.get("Subregion")),
                "country": DataService._clean_nan(row.get("Country")),
                "sampling_method": DataService._clean_nan(row.get("Sampling Method")),
                "organization": DataService._clean_nan(row.get("Organization")),
                "study_type": DataService._clean_nan(row.get("Study Type")),
            }
            
            # Upsert by unique_id to avoid duplicates
            operations.append(
                UpdateOne(
                    {"unique_id": doc["unique_id"]},
                    {"$set": doc},
                    upsert=True
                )
            )
            
            # Execute in batches to prevent memory overflow
            if len(operations) >= 1000:
                await collection.bulk_write(operations, ordered=False)
                operations = []
                
        # Write remaining
        if operations:
            await collection.bulk_write(operations, ordered=False)
            
        count = await collection.count_documents({})
        logger.info(f"Import complete. Total documents in collection: {count}")
        return {"status": "success", "total_documents": count}

    @staticmethod
    async def get_observations(
        skip: int = 0, 
        limit: int = 100,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        region: Optional[str] = None,
        ocean: Optional[str] = None,
        concentration_class: Optional[str] = None
    ) -> PaginatedResponse:
        collection = db_client.db["pollution_observations"]
        start_date, end_date = parse_date_range(start_date, end_date)
        
        query = {}
        if start_date or end_date:
            query["sample_date"] = {}
            if start_date: query["sample_date"]["$gte"] = start_date
            if end_date: query["sample_date"]["$lte"] = end_date
            
        if region:
            query["region"] = region
        if ocean:
            query["ocean"] = ocean
        if concentration_class:
            query["concentration_class"] = concentration_class
            
        cursor = collection.find(query, {"_id": 0}).skip(skip).limit(limit)
        results = await cursor.to_list(length=limit)
        total = await collection.count_documents(query)
        
        return PaginatedResponse(
            data=results,
            total=total,
            skip=skip,
            limit=limit
        )

    @staticmethod
    async def get_observation_by_id(unique_id: str) -> Optional[Dict[str, Any]]:
        collection = db_client.db["pollution_observations"]
        doc = await collection.find_one({"unique_id": unique_id}, {"_id": 0})
        return doc

    @staticmethod
    async def get_stats() -> Dict[str, Any]:
        collection = db_client.db["pollution_observations"]
        total = await collection.count_documents({})
        return {"total_observations": total}
