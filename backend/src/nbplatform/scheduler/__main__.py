"""`python -m nbplatform.scheduler`.

Reconcilia os cron jobs do APScheduler com os schedules habilitados no banco a
cada ciclo. Quando um cron dispara, cria um Job (via JobOrchestrator) — nunca
executa Papermill.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging

from nbplatform.core.config import get_settings
from nbplatform.core.logging import configure_logging
from nbplatform.core.runtime import heartbeat_loop, install_signal_handlers
from nbplatform.db.session import session_scope
from nbplatform.domain.schedule_spec import ScheduleSpec
from nbplatform.queue.redis_client import close_redis, get_redis, ping
from nbplatform.repositories.schedule_repository import ScheduleRepository
from nbplatform.scheduler.apscheduler_adapter import APSchedulerAdapter
from nbplatform.services.schedule_runner import run_due_schedule

logger = logging.getLogger(__name__)

RECONCILE_INTERVAL_S = 15


async def _load_specs() -> list[ScheduleSpec]:
    async with session_scope() as session:
        schedules = await ScheduleRepository(session).list_enabled()
        return [
            ScheduleSpec(id=str(s.id), cron=s.cron, timezone=s.timezone)
            for s in schedules
        ]


async def _reconcile_loop(adapter: APSchedulerAdapter, stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            await adapter.sync(await _load_specs())
        except Exception:
            logger.exception("erro ao reconciliar schedules")
        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=RECONCILE_INTERVAL_S)


async def _run() -> None:
    settings = get_settings()
    configure_logging(settings.log_level, service="scheduler")
    logger.info("scheduler up")

    if not await ping():
        logger.error("Redis indisponível no start; encerrando para reinício")
        raise SystemExit(1)

    redis = get_redis()

    async def _on_fire(schedule_id: str) -> None:
        await run_due_schedule(schedule_id, redis)

    adapter = APSchedulerAdapter()
    await adapter.start(on_fire=_on_fire)

    stop = asyncio.Event()
    install_signal_handlers(asyncio.get_running_loop(), stop)

    hb = asyncio.create_task(heartbeat_loop("scheduler", stop))
    reconcile = asyncio.create_task(_reconcile_loop(adapter, stop))
    try:
        await asyncio.gather(hb, reconcile)
    finally:
        stop.set()
        for task in (hb, reconcile):
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        await adapter.shutdown()
        await close_redis()
        logger.info("scheduler down")


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
