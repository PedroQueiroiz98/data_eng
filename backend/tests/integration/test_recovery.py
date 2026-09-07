from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from nbplatform.db.session import session_scope
from nbplatform.domain.enums import ExecutionStatus
from nbplatform.queue.execution_queue import ExecutionQueue
from nbplatform.queue.redis_client import get_redis
from nbplatform.services.execution_service import ExecutionService
from nbplatform.worker.recovery import recover_stale_executions
from tests.conftest import requires_services

pytestmark = [pytest.mark.asyncio, requires_services]


async def _make_running(client, *, attempt: int) -> uuid.UUID:
    nb = (await client.post("/api/notebooks", json={"name": "rec"})).json()
    ex = await client.post(f"/api/notebooks/{nb['id']}/execute", json={})
    exec_id = uuid.UUID(ex.json()["id"])
    stale_ts = datetime.now(UTC) - timedelta(hours=1)
    async with session_scope() as session:
        service = ExecutionService(session)
        execution = await service.mark_running(
            exec_id, worker_id="dead-worker", attempt=attempt
        )
        execution.last_heartbeat = stale_ts
    return exec_id


async def test_stale_running_is_requeued_with_backoff(client) -> None:
    exec_id = await _make_running(client, attempt=1)
    redis = get_redis()
    settings = ExecutionQueue(redis).settings
    before = await redis.zcard(settings.redis_queue_executions_delayed)

    recovered = await recover_stale_executions(redis)
    assert recovered >= 1

    async with session_scope() as session:
        execution = await ExecutionService(session).get(exec_id)
    assert execution.status == ExecutionStatus.QUEUED
    assert execution.attempt == 2
    assert execution.worker_id is None
    assert execution.error_code is None

    after = await redis.zcard(settings.redis_queue_executions_delayed)
    assert after == before + 1


async def test_stale_running_exhausted_goes_to_dlq(client) -> None:
    exec_id = await _make_running(client, attempt=3)  # > max_retries padrão (2)
    redis = get_redis()
    settings = ExecutionQueue(redis).settings
    dlq_before = await redis.llen(settings.redis_dlq_executions)

    await recover_stale_executions(redis)

    async with session_scope() as session:
        execution = await ExecutionService(session).get(exec_id)
    assert execution.status == ExecutionStatus.FAILED
    assert execution.error_code == "LEASE_EXPIRED"

    dlq_after = await redis.llen(settings.redis_dlq_executions)
    assert dlq_after == dlq_before + 1
