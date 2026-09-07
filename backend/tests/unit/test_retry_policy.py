from __future__ import annotations

import pytest

from nbplatform.domain.enums import ErrorClass, RetryMode
from nbplatform.domain.retry_policy import RetryPolicy


def test_exponential_backoff_matches_spec() -> None:
    p = RetryPolicy(max_retries=3, initial_delay_seconds=10, backoff_multiplier=2)
    assert p.delay_for_attempt(1) == 10
    assert p.delay_for_attempt(2) == 20
    assert p.delay_for_attempt(3) == 40


def test_backoff_capped_at_max_delay() -> None:
    p = RetryPolicy(
        max_retries=10, initial_delay_seconds=10, backoff_multiplier=2, max_delay_seconds=60
    )
    assert p.delay_for_attempt(5) == 60  # 10*16 = 160 -> capado


@pytest.mark.parametrize(
    ("attempt", "expected"),
    [(1, True), (2, True), (3, True), (4, False), (5, False)],
)
def test_should_retry_respects_max(attempt: int, expected: bool) -> None:
    p = RetryPolicy(max_retries=3, retry_mode=RetryMode.ANY)
    assert p.should_retry(attempt=attempt, error_class=ErrorClass.PERMANENT) is expected


def test_transient_only_mode() -> None:
    p = RetryPolicy(max_retries=3, retry_mode=RetryMode.TRANSIENT_ONLY)
    assert p.should_retry(attempt=1, error_class=ErrorClass.TRANSIENT) is True
    assert p.should_retry(attempt=1, error_class=ErrorClass.PERMANENT) is False
    assert p.should_retry(attempt=1, error_class=ErrorClass.UNKNOWN) is False


def test_any_mode_retries_all_classes() -> None:
    p = RetryPolicy(max_retries=2, retry_mode=RetryMode.ANY)
    for cls in ErrorClass:
        assert p.should_retry(attempt=1, error_class=cls) is True


def test_serialization_roundtrip() -> None:
    p = RetryPolicy(max_retries=5, initial_delay_seconds=3, retry_mode=RetryMode.ANY)
    assert RetryPolicy.from_dict(p.to_dict()) == p
    assert RetryPolicy.from_dict(None) == RetryPolicy()
    assert RetryPolicy.from_dict({"retry_mode": "ANY"}).retry_mode is RetryMode.ANY
