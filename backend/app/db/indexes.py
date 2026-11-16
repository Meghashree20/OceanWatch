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

        await db_client.db["users"].create_index("email", unique=True)

        await db_client.db["pollution_alerts"].create_index("event_key", unique=True)
        await db_client.db["pollution_alerts"].create_index([("status", pymongo.ASCENDING), ("last_updated_at", pymongo.DESCENDING)])
        await db_client.db["environmental_organizations"].create_index("contact_email", unique=True)
        await db_client.db["environmental_organizations"].create_index(
            [("service_area", pymongo.GEOSPHERE)]
        )
        await db_client.db["organization_notifications"].create_index(
            [("alert_id", pymongo.ASCENDING), ("organization_id", pymongo.ASCENDING)],
            unique=True,
        )

        cleanup_operations = db_client.db["cleanup_operations"]
        await cleanup_operations.create_index("operation_id", unique=True)
        await cleanup_operations.create_index(
            [("status", pymongo.ASCENDING), ("updated_at", pymongo.DESCENDING)]
        )
        await cleanup_operations.create_index("recommendation_id")
        await cleanup_operations.create_index(
            "active_recommendation_key",
            unique=True,
            sparse=True,
            name="unique_active_recommendation_operation",
        )
        cleanup_evidence = db_client.db["cleanup_operation_evidence"]
        await cleanup_evidence.create_index("evidence_id", unique=True)
        await cleanup_evidence.create_index(
            [("operation_id", pymongo.ASCENDING), ("created_at", pymongo.ASCENDING)]
        )
        await db_client.db["private_media"].create_index("media_id", unique=True)
        await db_client.db["cleanup_operation_notifications"].create_index(
            [("operation_id", pymongo.ASCENDING), ("organization_id", pymongo.ASCENDING)],
            unique=True,
        )
        await db_client.db["cleanup_operation_notifications"].create_index(
            [("delivery_status", pymongo.ASCENDING), ("updated_at", pymongo.DESCENDING)]
        )
        citizen_reports = db_client.db["citizen_reports"]
        await citizen_reports.create_index("report_id", unique=True)
        await citizen_reports.create_index(
            [("status", pymongo.ASCENDING), ("created_at", pymongo.DESCENDING)]
        )
        await citizen_reports.create_index(
            [("submitted_by", pymongo.ASCENDING), ("created_at", pymongo.DESCENDING)]
        )
        
        logger.info("Indexes created successfully!")
    except Exception as exc:
        logger.exception("Error creating MongoDB indexes")
        raise RuntimeError("MongoDB index creation failed") from exc
