from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient
from app.config import settings

# Async MongoDB client for FastAPI
async_mongo_client: AsyncIOMotorClient | None = None


def get_async_database():
    global async_mongo_client
    if async_mongo_client is None:
        async_mongo_client = AsyncIOMotorClient(settings.MONGODB_URL)
    return async_mongo_client[settings.MONGODB_DB_NAME]


# Synchronous MongoDB client for Celery tasks
_sync_mongo_client: MongoClient | None = None


def get_sync_database():
    global _sync_mongo_client
    if _sync_mongo_client is None:
        _sync_mongo_client = MongoClient(settings.MONGODB_URL)
    return _sync_mongo_client[settings.MONGODB_DB_NAME]
