from contextlib import asynccontextmanager
from typing import Any
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


@asynccontextmanager
async def lifespan(_app: Any):
    """Database lifecycle manager that provisions MongoDB indexes on application startup."""
    db = get_async_database()
    await db["users"].create_index("user_id", unique=True)
    await db["credit_tasks"].create_index("task_id", unique=True)
    await db["credit_tasks"].create_index([("user_id", 1), ("amount", 1), ("created_at", -1)])
    yield


# Synchronous MongoDB client for Celery tasks
_sync_mongo_client: MongoClient | None = None


def get_sync_database():
    global _sync_mongo_client
    if _sync_mongo_client is None:
        _sync_mongo_client = MongoClient(settings.MONGODB_URL)
    return _sync_mongo_client[settings.MONGODB_DB_NAME]
