from __future__ import annotations

import time

import pytest

from nbplatform.queue.execution_queue import ExecutionQueue
from nbplatform.queue.redis_client import get_redis
from tests.conftest import requires_services

pytestmark = [pytest.mark.asyncio, requires_services]


async def test_promote_due_moves_only_ready_entries() -> None:
    q = ExecutionQueue(get_redis())
    settings = q.settings
    redis = q.redis
    await redis.delete(
        settings.redis_queue_executions, settings.redis_queue_executions_delayed
    )

    await q.enqueue_delayed("past-1", attempt=2, ready_at=time.time() - 5)
    await q.enqueue_delayed("future-1", attempt=2, ready_at=time.time() + 3600)

    promoted = await q.promote_due()
    assert promoted == 1
    assert await redis.llen(settings.redis_queue_executions) == 1
    assert await redis.zcard(settings.redis_queue_executions_delayed) == 1

    msg = await q.lease(timeout_s=1)
    assert msg is not None
    assert msg.execution_id == "past-1"
    assert msg.attempt == 2
    await q.ack(msg)


async def test_promote_due_idempotent_when_nothing_ready() -> None:
    q = ExecutionQueue(get_redis())
    await q.redis.delete(q.settings.redis_queue_executions_delayed)
    await q.enqueue_delayed("x", attempt=1, ready_at=time.time() + 999)
    assert await q.promote_due() == 0
