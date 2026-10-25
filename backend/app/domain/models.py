from pydantic import BaseModel, Field


class CreditRequest(BaseModel):
    user_id: str = Field(..., min_length=1, description="Unique identifier for the user account")
    amount: float = Field(..., gt=0, description="Amount of credit to add (must be greater than 0)")


class CreditResponse(BaseModel):
    task_id: str
    message: str = "Credit request accepted and queued for processing"
    status: str = "processing"


class UserResponse(BaseModel):
    user_id: str
    balance: float = 0.0
    status: str
