from __future__ import annotations

import pytest

from nbplatform.domain.schedule_spec import ScheduleSpec
from nbplatform.scheduler.apscheduler_adapter import APSchedulerAdapter

pytestmark = pytest.mark.asyncio


async def _noop(_sid: str) -> None:
    return None


async def test_sync_adds_removes_and_reschedules() -> None:
    adapter = APSchedulerAdapter()
    await adapter.start(on_fire=_noop)
    try:
        await adapter.sync(
            [
                ScheduleSpec("a", "*/5 * * * *", "UTC"),
                ScheduleSpec("b", "0 * * * *", "UTC"),
            ]
        )
        ids = {j.id for j in adapter._scheduler.get_jobs()}
        assert ids == {"sched:a", "sched:b"}

        # remove b, mantém a, adiciona c
        await adapter.sync(
            [
                ScheduleSpec("a", "*/5 * * * *", "UTC"),
                ScheduleSpec("c", "30 2 * * *", "UTC"),
            ]
        )
        ids = {j.id for j in adapter._scheduler.get_jobs()}
        assert ids == {"sched:a", "sched:c"}

        # muda o cron de a → job recriado, ainda presente
        await adapter.sync([ScheduleSpec("a", "0 0 * * *", "UTC")])
        assert {j.id for j in adapter._scheduler.get_jobs()} == {"sched:a"}
        assert adapter._known["a"] == ("0 0 * * *", "UTC")
    finally:
        await adapter.shutdown()
