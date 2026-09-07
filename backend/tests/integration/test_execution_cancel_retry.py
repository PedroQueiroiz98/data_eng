from __future__ import annotations

import uuid

import pytest

from nbplatform.db.session import session_scope
from nbplatform.domain.enums import ExecutionStatus
from nbplatform.services.execution_service import ExecutionService
from tests.conftest import requires_services

pytestmark = [pytest.mark.asyncio, requires_services]


async def _queued_execution(client) -> str:
    nb = (await client.post("/api/notebooks", json={"name": "cr"})).json()
    ex = await client.post(f"/api/notebooks/{nb['id']}/execute", json={})
    assert ex.status_code == 202
    return ex.json()["id"]


async def _failed_execution(client) -> str:
    exec_id = await _queued_execution(client)
    async with session_scope() as session:
        svc = ExecutionService(session)
        await svc.mark_running(uuid.UUID(exec_id), worker_id="w", attempt=1)
        await svc.finish(
            uuid.UUID(exec_id),
            status=ExecutionStatus.FAILED,
            error_code="NOTEBOOK_ERROR",
            error_message="NameError: boom",
        )
    return exec_id


async def test_cancel_queued_is_idempotent(client) -> None:
    exec_id = await _queued_execution(client)

    first = await client.post(f"/api/executions/{exec_id}/cancel")
    assert first.status_code == 200
    assert first.json()["status"] == "CANCELLED"

    second = await client.post(f"/api/executions/{exec_id}/cancel")
    assert second.status_code == 200
    assert second.json()["status"] == "CANCELLED"


async def test_retry_requires_terminal_failure(client) -> None:
    exec_id = await _queued_execution(client)
    # ainda QUEUED → não pode refazer
    resp = await client.post(f"/api/executions/{exec_id}/retry")
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "conflict"


async def test_retry_failed_execution_requeues_with_next_attempt(client) -> None:
    exec_id = await _failed_execution(client)
    resp = await client.post(f"/api/executions/{exec_id}/retry")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "QUEUED"
    assert body["attempt"] == 2

    detail = (await client.get(f"/api/executions/{exec_id}")).json()
    assert detail["status"] == "QUEUED"
    assert detail["attempt"] == 2
    assert detail["error_code"] is None
    assert detail["error_message"] is None


async def test_cancelled_execution_cannot_be_retried(client) -> None:
    exec_id = await _queued_execution(client)
    assert (await client.post(f"/api/executions/{exec_id}/cancel")).status_code == 200

    retry = await client.post(f"/api/executions/{exec_id}/retry")
    assert retry.status_code == 409  # CANCELLED é terminal; dispare o notebook de novo
