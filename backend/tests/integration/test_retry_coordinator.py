from __future__ import annotations

import uuid

import pytest

from nbplatform.db.session import session_scope
from nbplatform.domain.enums import ExecutionStatus
from nbplatform.services.execution_service import ExecutionService
from nbplatform.services.retry_coordinator import RetryCoordinator
from tests.conftest import requires_services

pytestmark = [pytest.mark.asyncio, requires_services]


async def _failed_execution(client, error_message: str) -> uuid.UUID:
    nb = (await client.post("/api/notebooks", json={"name": "rc"})).json()
    ex = await client.post(f"/api/notebooks/{nb['id']}/execute", json={})
    exec_id = uuid.UUID(ex.json()["id"])
    async with session_scope() as session:
        service = ExecutionService(session)
        await service.mark_running(exec_id, worker_id="w", attempt=1)
        await service.finish(
            exec_id,
            status=ExecutionStatus.FAILED,
            error_code="NOTEBOOK_ERROR",
            error_message=error_message,
        )
    return exec_id


async def test_transient_failure_is_retried(client) -> None:
    exec_id = await _failed_execution(client, "OperationalError: could not connect to server")
    async with session_scope() as session:
        decision = await RetryCoordinator(session).decide_and_apply(
            exec_id,
            failed_status=ExecutionStatus.FAILED,
            error_code="NOTEBOOK_ERROR",
            error_message="OperationalError: could not connect to server",
        )
    assert decision.action == "retry"
    assert decision.next_attempt == 2
    assert decision.delay_s == 10  # initial_delay padrão

    async with session_scope() as session:
        execution = await ExecutionService(session).get(exec_id)
    assert execution.status == ExecutionStatus.QUEUED
    assert execution.attempt == 2


async def test_permanent_failure_goes_dead(client) -> None:
    exec_id = await _failed_execution(client, "NameError: name 'foo' is not defined")
    async with session_scope() as session:
        decision = await RetryCoordinator(session).decide_and_apply(
            exec_id,
            failed_status=ExecutionStatus.FAILED,
            error_code="NOTEBOOK_ERROR",
            error_message="NameError: name 'foo' is not defined",
        )
    assert decision.action == "dead"

    async with session_scope() as session:
        execution = await ExecutionService(session).get(exec_id)
    assert execution.status == ExecutionStatus.FAILED
    assert execution.attempt == 1
