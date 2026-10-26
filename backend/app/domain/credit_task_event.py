from datetime import datetime, timezone
from enum import StrEnum
from typing import Optional
import uuid
from pydantic import BaseModel, Field, field_validator


class TaskStatus(StrEnum):
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED_DUPLICATE = "failed_duplicate"
    REVOKED_DUPLICATE = "revoked_duplicate"
    FAILED = "failed"


class CreditTaskEvent(BaseModel):
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique task identifier")
    user_id: str = Field(..., min_length=1, description="Unique user identifier")
    amount: float = Field(..., gt=0, description="Credit amount to apply")
    status: str = Field(default=TaskStatus.PROCESSING, description="Lifecycle status of the credit task")
    error_message: Optional[str] = Field(default=None, description="Optional error or failure reason")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("created_at", "updated_at", mode="after")
    @classmethod
    def ensure_tz_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    @property
    def had_failed(self):
        return self.status in (TaskStatus.FAILED_DUPLICATE, TaskStatus.REVOKED_DUPLICATE)
