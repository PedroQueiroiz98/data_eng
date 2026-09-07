from __future__ import annotations

import uuid

import pytest

from nbplatform.db.session import session_scope
from nbplatform.queue.redis_client import get_redis
from nbplatform.repositories.schedule_repository import ScheduleRepository
from nbplatform.services.schedule_runner import run_due_schedule
from tests.conftest import requires_services
from tests.integration.helpers import make_notebook, make_workflow, notebook_content

pytestmark = [pytest.mark.asyncio, requires_services]


async def _schedule(client, *, enabled: bool = True) -> str:
    nb = await make_notebook(client, "sr", notebook_content("print(1)"))
    wf = await make_workflow(
        client, "wf-sr", [{"key": "a", "name": "A", "notebook_id": nb}], []
    )
    resp = await client.post(
        "/api/schedules",
        json={"workflow_id": wf, "cron": "*/5 * * * *", "enabled": enabled},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def test_run_due_schedule_creates_scheduled_job(client) -> None:
    sched_id = await _schedule(client)
    job_id = await run_due_schedule(sched_id, get_redis())
    assert job_id is not None

    detail = (await client.get(f"/api/jobs/{job_id}")).json()
    assert detail["trigger_type"] == "SCHEDULED"

    async with session_scope() as session:
        schedule = await ScheduleRepository(session).get(uuid.UUID(sched_id))
        assert schedule.last_run_at is not None
        assert schedule.next_run_at is not None

    # segundo disparo imediato é ignorado (min interval)
    assert await run_due_schedule(sched_id, get_redis()) is None


async def test_disabled_schedule_does_not_fire(client) -> None:
    sched_id = await _schedule(client, enabled=False)
    assert await run_due_schedule(sched_id, get_redis()) is None
