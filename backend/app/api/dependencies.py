from fastapi import Depends
from app.domain.interfaces import IUserInterface
from app.infrastructure.repositories.user_repository import MongoUserRepository
from app.infrastructure.tasks import enqueue_credit_task
from app.use_cases.user_credit_service import UserCreditService


def get_user_repository() -> IUserInterface:
    return MongoUserRepository()


def get_user_credit_service(
    repo: IUserInterface = Depends(get_user_repository),
) -> UserCreditService:
    return UserCreditService(
        user_repository=repo,
        enqueue_callback=enqueue_credit_task,
    )
