from __future__ import annotations

import pytest

from nbplatform.core.errors import ConflictError
from nbplatform.domain.enums import JobStatus as J
from nbplatform.domain.enums import JobTaskStatus as T
from nbplatform.domain.job_state import (
    JOB_TERMINAL,
    JOBTASK_BLOCKING_FAILURE,
    JOBTASK_TERMINAL,
    assert_job_transition,
    job_can_transition,
    task_can_transition,
)


def test_terminal_sets() -> None:
    assert {J.SUCCESS, J.FAILED, J.CANCELLED} == JOB_TERMINAL
    assert {T.SUCCESS, T.FAILED, T.CANCELLED, T.SKIPPED} == JOBTASK_TERMINAL
    assert {T.FAILED, T.CANCELLED, T.SKIPPED} == JOBTASK_BLOCKING_FAILURE
    assert T.SUCCESS not in JOBTASK_BLOCKING_FAILURE


@pytest.mark.parametrize(
    ("cur", "tgt", "ok"),
    [
        (J.QUEUED, J.RUNNING, True),
        (J.RUNNING, J.SUCCESS, True),
        (J.RUNNING, J.FAILED, True),
        (J.FAILED, J.RUNNING, True),  # retry
        (J.SUCCESS, J.RUNNING, False),
        (J.SUCCESS, J.FAILED, False),
    ],
)
def test_job_transitions(cur: J, tgt: J, ok: bool) -> None:
    assert job_can_transition(cur, tgt) is ok
    if ok:
        assert_job_transition(cur, tgt)
    else:
        with pytest.raises(ConflictError):
            assert_job_transition(cur, tgt)


def test_task_transitions() -> None:
    assert task_can_transition(T.PENDING, T.QUEUED)
    assert task_can_transition(T.PENDING, T.SKIPPED)
    assert task_can_transition(T.RUNNING, T.SUCCESS)
    assert task_can_transition(T.FAILED, T.PENDING)  # retry de job
    assert not task_can_transition(T.SUCCESS, T.RUNNING)
