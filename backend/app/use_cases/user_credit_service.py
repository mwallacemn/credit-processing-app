from typing import Callable, Optional

from app.api.schemas import CreditRequest, CreditResponse
from app.domain.credit_task_event import CreditTaskEvent, TaskStatus
from app.domain.interfaces import IUserInterface
from app.domain.user import User, UserStatus


class UserCreditService:
    """
    Dedicated application use-case service for the API presentation layer:
    - Ingests credit requests, records credit task events, and dispatches background tasks
    - Queries user account state and credit task event status
    """

    def __init__(
        self,
        user_repository: IUserInterface,
        enqueue_callback: Optional[Callable[[str], None]] = None,
    ):
        self._repo = user_repository
        self._enqueue_callback = enqueue_callback

    async def submit_credit(self, request: CreditRequest) -> CreditResponse:
        # 1. Convert request DTO into a domain CreditTaskEvent (status='processing')
        task_event = request.to_event()
        await self._repo.create_credit_task(task_event)

        # 2. Set the user's MongoDB record status to 'processing'
        await self._repo.update_user_status(request.user_id, UserStatus.PROCESSING)

        # 3. Dispatch background task with a reference to the credit task_id
        if self._enqueue_callback:
            self._enqueue_callback(task_event.task_id)

        return CreditResponse.from_event(task_event)

    async def get_user(self, user_id: str) -> Optional[User]:
        return await self._repo.get_user(user_id)

    async def get_task_event(self, task_id: str) -> Optional[CreditTaskEvent]:
        return await self._repo.get_credit_task(task_id)
