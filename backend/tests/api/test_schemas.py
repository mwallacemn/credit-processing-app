import pytest
from pydantic import ValidationError

from app.api.schemas import CreditRequest, CreditResponse, UserResponse
from app.domain.credit_task_event import CreditTaskEvent, TaskStatus
from app.domain.user import User, UserStatus


def test_credit_request_validation():
    with pytest.raises(ValidationError):
        CreditRequest(user_id="", amount=50.0)

    with pytest.raises(ValidationError):
        CreditRequest(user_id="u_123", amount=0.0)

    with pytest.raises(ValidationError):
        CreditRequest(user_id="u_123", amount=-25.0)


def test_model_and_schema_reusability_helpers():
    # 1. CreditRequest -> CreditTaskEvent
    req = CreditRequest(user_id="u_123", amount=150.0)
    event = req.to_event()
    assert isinstance(event, CreditTaskEvent)
    assert event.user_id == "u_123"
    assert event.amount == 150.0
    assert event.status == TaskStatus.PROCESSING

    # 2. CreditTaskEvent -> CreditResponse
    res = CreditResponse.from_event(event)
    assert isinstance(res, CreditResponse)
    assert res.task_id == event.task_id
    assert res.status == event.status

    # 3. User -> UserResponse via from_user and model_validate (from_attributes)
    user = User(user_id="u_123", balance=250.0, status=UserStatus.PROCESSED)
    user_res_from_helper = UserResponse.from_user(user)
    assert user_res_from_helper.user_id == "u_123"
    assert user_res_from_helper.balance == 250.0

    user_res_from_validate = UserResponse.model_validate(user)
    assert user_res_from_validate.user_id == "u_123"
    assert user_res_from_validate.balance == 250.0
