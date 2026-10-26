from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional

from app.domain.credit_task_event import CreditTaskEvent
from app.domain.user import User


class IUserInterface(ABC):
    """Port interface connecting Domain/Use-Cases to User & CreditTaskEvent persistence."""

    @abstractmethod
    async def get_user(self, user_id: str) -> Optional[User]:
        pass

    @abstractmethod
    async def update_user_status(self, user_id: str, status: str) -> User:
        pass

    @abstractmethod
    async def increment_user_balance(self, user_id: str, amount: float, status: str = "processed") -> User:
        pass

    @abstractmethod
    async def create_credit_task(self, task_event: CreditTaskEvent) -> CreditTaskEvent:
        pass

    @abstractmethod
    async def get_credit_task(self, task_id: str) -> Optional[CreditTaskEvent]:
        pass

    @abstractmethod
    async def update_credit_task_status(
        self, task_id: str, status: str, error_message: Optional[str] = None
    ) -> Optional[CreditTaskEvent]:
        pass

    @abstractmethod
    async def find_recent_tasks_by_amount(
        self, user_id: str, amount: float, since: datetime, exclude_task_id: Optional[str] = None
    ) -> List[CreditTaskEvent]:
        pass

    @abstractmethod
    async def count_active_tasks_for_user(self, user_id: str, exclude_task_id: Optional[str] = None) -> int:
        pass
