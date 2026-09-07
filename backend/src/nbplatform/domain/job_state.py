"""Estados de Job e JobTask + transições válidas."""

from __future__ import annotations

from nbplatform.core.errors import ConflictError
from nbplatform.domain.enums import JobStatus, JobTaskStatus

_J = JobStatus
_T = JobTaskStatus

_JOB_TRANSITIONS: dict[JobStatus, frozenset[JobStatus]] = {
    _J.QUEUED: frozenset({_J.RUNNING, _J.CANCELLED}),
    _J.RUNNING: frozenset({_J.SUCCESS, _J.FAILED, _J.CANCELLED}),
    _J.SUCCESS: frozenset(),
    _J.FAILED: frozenset({_J.RUNNING}),  # retry
    _J.CANCELLED: frozenset({_J.RUNNING}),  # retry
}

_TASK_TRANSITIONS: dict[JobTaskStatus, frozenset[JobTaskStatus]] = {
    _T.PENDING: frozenset({_T.QUEUED, _T.SKIPPED, _T.CANCELLED}),
    _T.QUEUED: frozenset({_T.RUNNING, _T.CANCELLED, _T.FAILED}),
    _T.RUNNING: frozenset({_T.SUCCESS, _T.FAILED, _T.CANCELLED, _T.SKIPPED}),
    _T.SUCCESS: frozenset({_T.PENDING}),  # retry de job re-arma tasks
    _T.FAILED: frozenset({_T.PENDING}),
    _T.CANCELLED: frozenset({_T.PENDING}),
    _T.SKIPPED: frozenset({_T.PENDING}),
}

JOB_TERMINAL: frozenset[JobStatus] = frozenset({_J.SUCCESS, _J.FAILED, _J.CANCELLED})
JOBTASK_TERMINAL: frozenset[JobTaskStatus] = frozenset(
    {_T.SUCCESS, _T.FAILED, _T.CANCELLED, _T.SKIPPED}
)
JOBTASK_BLOCKING_FAILURE: frozenset[JobTaskStatus] = frozenset(
    {_T.FAILED, _T.CANCELLED, _T.SKIPPED}
)


def job_can_transition(current: JobStatus, target: JobStatus) -> bool:
    return target in _JOB_TRANSITIONS.get(current, frozenset())


def assert_job_transition(current: JobStatus, target: JobStatus) -> None:
    if not job_can_transition(current, target):
        raise ConflictError(f"Transição de Job inválida: {current} → {target}.")


def task_can_transition(current: JobTaskStatus, target: JobTaskStatus) -> bool:
    return target in _TASK_TRANSITIONS.get(current, frozenset())
