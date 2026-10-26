from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.use_cases.credit_task_service import CreditTaskService
    from app.use_cases.user_credit_service import UserCreditService

__all__ = ["CreditTaskService", "UserCreditService"]


def __getattr__(name: str):
    if name == "CreditTaskService":
        from app.use_cases.credit_task_service import CreditTaskService

        return CreditTaskService
    if name == "UserCreditService":
        from app.use_cases.user_credit_service import UserCreditService

        return UserCreditService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
