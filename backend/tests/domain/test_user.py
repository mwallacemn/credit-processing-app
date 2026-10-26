import pytest
from pydantic import ValidationError

from app.domain.user import User, UserStatus


def test_user_model_defaults():
    user = User(user_id="u_123")
    assert user.user_id == "u_123"
    assert user.balance == 0.0
    assert user.status == UserStatus.UNKNOWN


def test_user_model_rejects_empty_user_id():
    with pytest.raises(ValidationError):
        User(user_id="")


def test_user_status_str_enum_values():
    assert UserStatus.UNKNOWN == "unknown"
    assert UserStatus.PROCESSING == "processing"
    assert UserStatus.PROCESSED == "processed"
    assert UserStatus.FAILED == "failed"
