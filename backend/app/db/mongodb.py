from motor.motor_asyncio import AsyncIOMotorClient
from typing import Any, Optional
from app.core.config import settings
from app.core.logging_config import logger

class MongoDB:
    client: Optional[AsyncIOMotorClient] = None
    db: Any = None

db_client = MongoDB()

async def connect_to_mongo():
    logger.info("Connecting to MongoDB...")
    client = AsyncIOMotorClient(
        settings.MONGODB_URL,
        serverSelectionTimeoutMS=settings.MONGODB_SERVER_SELECTION_TIMEOUT_MS,
        connectTimeoutMS=settings.MONGODB_CONNECT_TIMEOUT_MS,
    )
    try:
        await client.admin.command("ping")
    except Exception as exc:
        client.close()
        logger.exception("MongoDB connection failed")
        raise RuntimeError("MongoDB is unavailable") from exc
    db_client.client = client
    db_client.db = client[settings.MONGODB_DB_NAME]
    logger.info("Connected to MongoDB")

async def close_mongo_connection():
    logger.info("Closing MongoDB connection...")
    if db_client.client:
        db_client.client.close()
        db_client.client = None
        db_client.db = None
    logger.info("MongoDB connection closed!")
