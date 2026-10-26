from pydantic import BaseModel, ConfigDict, Field

from app.domain.credit_task_event import CreditTaskEvent, TaskStatus
from app.domain.user import User


class CreditRequest(BaseModel):
    user_id: str = Field(..., min_length=1, description="Unique identifier for the user account")
    amount: float = Field(..., gt=0, description="Amount of credit to add (must be greater than 0)")

    def to_event(self) -> CreditTaskEvent:
        """Convert request DTO into domain CreditTaskEvent."""
        return CreditTaskEvent(
            user_id=self.user_id,
            amount=self.amount,
            status=TaskStatus.PROCESSING,
        )


class CreditResponse(BaseModel):
    task_id: str
    message: str = "Credit request accepted and queued for processing"
    status: str = "processing"

    @classmethod
    def from_event(
        cls,
        event: CreditTaskEvent,
        message: str = "Credit request accepted and queued for processing",
    ) -> "CreditResponse":
        """Instantiate response DTO directly from domain CreditTaskEvent."""
        return cls(
            task_id=event.task_id,
            status=event.status,
            message=message,
        )


class UserResponse(BaseModel):
    """User account response DTO, reusable with the domain User model."""

    user_id: str = Field(..., min_length=1, description="Unique identifier for user")
    balance: float = Field(default=0.0, description="Account credit balance")
    status: str = Field(default="unknown", description="User processing status")

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_user(cls, user: User) -> "UserResponse":
        """Instantiate response DTO directly from domain User model."""
        return cls(
            user_id=user.user_id,
            balance=user.balance,
            status=user.status,
        )
