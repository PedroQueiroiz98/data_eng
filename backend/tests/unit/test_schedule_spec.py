from __future__ import annotations

from datetime import UTC, datetime

import pytest

from nbplatform.core.errors import DomainValidationError
from nbplatform.domain.schedule_spec import next_run_after, validate_cron


def test_valid_cron_passes() -> None:
    validate_cron("*/5 * * * *")
    validate_cron("0 3 * * 1", "America/Sao_Paulo")


def test_invalid_cron_rejected() -> None:
    with pytest.raises(DomainValidationError, match="cron"):
        validate_cron("not a cron")
    with pytest.raises(DomainValidationError, match="cron"):
        validate_cron("99 99 * * *")


def test_invalid_timezone_rejected() -> None:
    with pytest.raises(DomainValidationError, match="Timezone"):
        validate_cron("* * * * *", "Mars/Olympus")


def test_next_run_is_in_the_future() -> None:
    now = datetime(2026, 1, 1, 10, 7, 30, tzinfo=UTC)
    nxt = next_run_after("*/15 * * * *", "UTC", after=now)
    assert nxt is not None
    assert nxt > now
    assert nxt.minute in (0, 15, 30, 45)
