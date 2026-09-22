import pymongo
from app.db.mongodb import db_client
from app.core.logging_config import logger

async def create_indexes():
    """
    Creates necessary MongoDB indexes for performance.
    """
    try:
        collection = db_client.db["pollution_observations"]
        
        logger.info("Creating indexes for pollution_observations...")
        
        # Unique ID index
        await collection.create_index("unique_id", unique=True)
        
        await collection.create_index("sample_date")
        await collection.create_index("region")
        await collection.create_index("ocean")
        await collection.create_index("concentration_class")
        await collection.create_index([("latitude", pymongo.ASCENDING), ("longitude", pymongo.ASCENDING)])
        await collection.create_index([("region", pymongo.ASCENDING), ("sample_date", pymongo.ASCENDING)])

        hotspot_collection = db_client.db["hotspot_results"]
        await hotspot_collection.create_index("cluster_id")
        await hotspot_collection.create_index([("detection_run_id", pymongo.ASCENDING), ("cluster_id", pymongo.ASCENDING)], unique=True)
        await hotspot_collection.create_index("severity")
        await hotspot_collection.create_index([("region", pymongo.ASCENDING), ("ocean", pymongo.ASCENDING)])

        await db_client.db["hotspot_detection_runs"].create_index("run_id", unique=True)
        await db_client.db["hotspot_detection_runs"].create_index([("created_at", pymongo.DESCENDING)])
        
        logger.info("Indexes created successfully!")
    except Exception as exc:
        logger.exception("Error creating MongoDB indexes")
        raise RuntimeError("MongoDB index creation failed") from exc
