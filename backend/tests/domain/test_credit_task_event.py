from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from app.domain.credit_task_event import CreditTaskEvent, TaskStatus


def test_credit_task_event_defaults_and_tz_normalization():
    # Naive datetime should be normalized to UTC
    naive_dt = datetime(2026, 10, 25, 12, 0, 0)
    event = CreditTaskEvent(
        user_id="u_123",
        amount=100.0,
        created_at=naive_dt,
    )
    assert event.status == TaskStatus.PROCESSING
    assert len(event.task_id) > 0
    assert event.created_at.tzinfo == timezone.utc
    assert event.updated_at.tzinfo == timezone.utc


def test_task_status_excludes_pending():
    statuses = list(TaskStatus)
    assert "pending" not in statuses
    assert TaskStatus.PROCESSING == "processing"
    assert TaskStatus.PROCESSED == "processed"
    assert TaskStatus.FAILED_DUPLICATE == "failed_duplicate"
    assert TaskStatus.REVOKED_DUPLICATE == "revoked_duplicate"


@pytest.mark.parametrize(
    ("status", "expected_had_failed"),
    [
        (TaskStatus.FAILED_DUPLICATE, True),
        (TaskStatus.REVOKED_DUPLICATE, True),
        (TaskStatus.PROCESSING, False),
        (TaskStatus.PROCESSED, False),
        (TaskStatus.FAILED, False),
    ],
)
def test_credit_task_event_had_failed_property(status, expected_had_failed):
    event = CreditTaskEvent(user_id="u_123", amount=50.0, status=status)
    assert event.had_failed is expected_had_failed


def test_credit_task_event_validation_rejects_invalid_fields():
    with pytest.raises(ValidationError):
        CreditTaskEvent(user_id="", amount=50.0)

    with pytest.raises(ValidationError):
        CreditTaskEvent(user_id="u_123", amount=0.0)

    with pytest.raises(ValidationError):
        CreditTaskEvent(user_id="u_123", amount=-10.0)
