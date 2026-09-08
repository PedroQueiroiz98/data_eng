"""Máquina de estados da Execution. Transições inválidas são rejeitadas."""

from __future__ import annotations

from nbplatform.core.errors import ConflictError
from nbplatform.domain.enums import ExecutionStatus

_S = ExecutionStatus

# Transições permitidas. Base: contexto mestre
#   QUEUED → RUNNING
#   RUNNING → SUCCESS | FAILED | CANCELLED | TIMEOUT
#   FAILED → QUEUED (retry)
# Extensões seguras: cancelar antes de começar; re-enfileirar após TIMEOUT (retry, Fase 4).
_EXECUTION_TRANSITIONS: dict[ExecutionStatus, frozenset[ExecutionStatus]] = {
    _S.QUEUED: frozenset({_S.RUNNING, _S.CANCELLED}),
    _S.RUNNING: frozenset({_S.SUCCESS, _S.FAILED, _S.CANCELLED, _S.TIMEOUT}),
    _S.SUCCESS: frozenset(),
    _S.FAILED: frozenset({_S.QUEUED}),
    _S.TIMEOUT: frozenset({_S.QUEUED}),
    _S.CANCELLED: frozenset(),
}

TERMINAL_EXECUTION_STATES: frozenset[ExecutionStatus] = frozenset({_S.SUCCESS, _S.CANCELLED})


def can_transition(current: ExecutionStatus, target: ExecutionStatus) -> bool:
    return target in _EXECUTION_TRANSITIONS.get(current, frozenset())


def assert_transition(current: ExecutionStatus, target: ExecutionStatus) -> None:
    if not can_transition(current, target):
        raise ConflictError(f"Transição de execução inválida: {current} → {target}.")


def is_terminal(status: ExecutionStatus) -> bool:
    return not _EXECUTION_TRANSITIONS.get(status, frozenset())
