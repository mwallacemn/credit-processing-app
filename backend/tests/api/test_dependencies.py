from unittest.mock import MagicMock, patch

from app.api.dependencies import get_user_credit_service, get_user_repository
from app.domain.interfaces import IUserInterface
from app.infrastructure.repositories.user_repository import MongoUserRepository
from app.infrastructure.tasks import enqueue_credit_task
from app.use_cases.user_credit_service import UserCreditService


@patch("app.api.dependencies.MongoUserRepository")
def test_get_user_repository_returns_mongo_repository(mock_repo_cls):
    mock_instance = MagicMock(spec=MongoUserRepository)
    mock_repo_cls.return_value = mock_instance

    repo = get_user_repository()
    assert repo is mock_instance
    mock_repo_cls.assert_called_once_with()


def test_get_user_credit_service_wires_repository_and_enqueue_callback():
    mock_repo = MagicMock(spec=IUserInterface)
    service = get_user_credit_service(repo=mock_repo)

    assert isinstance(service, UserCreditService)
    assert service._repo is mock_repo
    assert service._enqueue_callback is enqueue_credit_task
