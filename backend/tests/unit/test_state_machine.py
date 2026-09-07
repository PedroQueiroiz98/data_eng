from __future__ import annotations

import pytest

from nbplatform.core.errors import ConflictError
from nbplatform.domain.enums import ExecutionStatus as S
from nbplatform.domain.state_machine import (
    assert_transition,
    can_transition,
    is_terminal,
)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (S.QUEUED, S.RUNNING),
        (S.QUEUED, S.CANCELLED),
        (S.RUNNING, S.SUCCESS),
        (S.RUNNING, S.FAILED),
        (S.RUNNING, S.CANCELLED),
        (S.RUNNING, S.TIMEOUT),
        (S.FAILED, S.QUEUED),
        (S.TIMEOUT, S.QUEUED),
    ],
)
def test_valid_transitions(current: S, target: S) -> None:
    assert can_transition(current, target) is True
    assert_transition(current, target)  # não levanta


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (S.QUEUED, S.SUCCESS),
        (S.SUCCESS, S.RUNNING),
        (S.CANCELLED, S.RUNNING),
        (S.SUCCESS, S.FAILED),
        (S.RUNNING, S.QUEUED),
    ],
)
def test_invalid_transitions_raise(current: S, target: S) -> None:
    assert can_transition(current, target) is False
    with pytest.raises(ConflictError):
        assert_transition(current, target)


def test_terminal_states() -> None:
    assert is_terminal(S.SUCCESS) is True
    assert is_terminal(S.CANCELLED) is True
    assert is_terminal(S.RUNNING) is False
    # FAILED/TIMEOUT não são terminais: permitem retry
    assert is_terminal(S.FAILED) is False
    assert is_terminal(S.TIMEOUT) is False
