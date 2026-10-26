from datetime import datetime, timezone
from typing import List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

from app.domain.credit_task_event import CreditTaskEvent, TaskStatus
from app.domain.interfaces import IUserInterface
from app.domain.user import User, UserStatus
from app.infrastructure.db.database import get_async_database


class MongoUserRepository(IUserInterface):
    """Concrete MongoDB repository managing users and credit_tasks collections."""

    def __init__(self, db: Optional[AsyncIOMotorDatabase] = None):
        self._db = db if db is not None else get_async_database()
        self._users = self._db["users"]
        self._tasks = self._db["credit_tasks"]

    async def get_user(self, user_id: str) -> Optional[User]:
        doc = await self._users.find_one({"user_id": user_id}, {"_id": 0})
        if not doc:
            return None
        return User(**doc)

    async def update_user_status(self, user_id: str, status: str) -> User:
        doc = await self._users.find_one_and_update(
            {"user_id": user_id},
            {"$set": {"status": status}},
            upsert=True,
            return_document=ReturnDocument.AFTER,
            projection={"_id": 0},
        )
        return User(
            user_id=doc["user_id"],
            balance=doc.get("balance", 0.0),
            status=doc.get("status", status),
        )

    async def increment_user_balance(
        self, user_id: str, amount: float, status: str = UserStatus.PROCESSED
    ) -> User:
        doc = await self._users.find_one_and_update(
            {"user_id": user_id},
            {
                "$inc": {"balance": amount},
                "$set": {"status": status},
            },
            upsert=True,
            return_document=ReturnDocument.AFTER,
            projection={"_id": 0},
        )
        return User(
            user_id=doc["user_id"],
            balance=doc.get("balance", 0.0),
            status=doc.get("status", status),
        )

    async def create_credit_task(self, task_event: CreditTaskEvent) -> CreditTaskEvent:
        if task_event.status != TaskStatus.PROCESSING:
            raise ValueError(
                f"New CreditTaskEvent must be created with status='{TaskStatus.PROCESSING}', "
                f"got '{task_event.status}'."
            )
        await self._tasks.insert_one(task_event.model_dump())
        return task_event

    async def get_credit_task(self, task_id: str) -> Optional[CreditTaskEvent]:
        doc = await self._tasks.find_one({"task_id": task_id}, {"_id": 0})
        if not doc:
            return None
        return CreditTaskEvent(**doc)

    async def update_credit_task_status(
        self, task_id: str, status: str, error_message: Optional[str] = None
    ) -> Optional[CreditTaskEvent]:
        """
        Atomically transitions a task out of 'processing'.
        Prevents records already in terminal states (e.g. 'revoked_duplicate',
        'failed_duplicate', 'processed') from being overwritten.
        """
        update_fields: dict = {
            "status": status,
            "updated_at": datetime.now(timezone.utc),
        }
        if error_message is not None:
            update_fields["error_message"] = error_message

        doc = await self._tasks.find_one_and_update(
            {
                "task_id": task_id,
                "status": TaskStatus.PROCESSING,
            },
            {"$set": update_fields},
            return_document=ReturnDocument.AFTER,
            projection={"_id": 0},
        )
        return CreditTaskEvent(**doc) if doc else None

    async def find_recent_tasks_by_amount(
        self, user_id: str, amount: float, since: datetime, exclude_task_id: Optional[str] = None
    ) -> List[CreditTaskEvent]:
        query: dict = {
            "user_id": user_id,
            "amount": amount,
            "created_at": {"$gte": since},
            "status": {
                "$in": [
                    TaskStatus.PROCESSING,
                    TaskStatus.PROCESSED,
                ]
            },
        }
        if exclude_task_id:
            query["task_id"] = {"$ne": exclude_task_id}

        cursor = self._tasks.find(query, {"_id": 0}).sort("created_at", 1)
        docs = await cursor.to_list(length=100)
        return [CreditTaskEvent(**doc) for doc in docs]

    async def count_active_tasks_for_user(self, user_id: str, exclude_task_id: Optional[str] = None) -> int:
        query: dict = {
            "user_id": user_id,
            "status": TaskStatus.PROCESSING,
        }
        if exclude_task_id:
            query["task_id"] = {"$ne": exclude_task_id}
        return await self._tasks.count_documents(query)
