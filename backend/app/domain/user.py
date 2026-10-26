from enum import StrEnum
from pydantic import BaseModel, Field


class UserStatus(StrEnum):
    UNKNOWN = "unknown"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"


class User(BaseModel):
    user_id: str = Field(..., min_length=1, description="Unique identifier for the user account")
    balance: float = Field(default=0.0, description="Account credit balance")
    status: str = Field(default=UserStatus.UNKNOWN, description="User processing status")
