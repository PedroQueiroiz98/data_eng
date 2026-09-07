"""`python -m nbplatform.scheduler`.

Fase 1: sobe um APScheduler vazio e publica heartbeat. O registro de schedules
(cron -> criar Job) chega na Fase 7.
"""

from __future__ import annotations

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from nbplatform.core.config import get_settings
from nbplatform.core.logging import configure_logging
from nbplatform.core.runtime import heartbeat_loop, install_signal_handlers
from nbplatform.queue.redis_client import close_redis, ping

logger = logging.getLogger(__name__)


async def _run() -> None:
    settings = get_settings()
    configure_logging(settings.log_level, service="scheduler")
    logger.info("scheduler up")

    if not await ping():
        logger.error("Redis indisponível no start; encerrando para reinício")
        raise SystemExit(1)

    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.start()

    stop = asyncio.Event()
    install_signal_handlers(asyncio.get_running_loop(), stop)

    try:
        await heartbeat_loop("scheduler", stop)
    finally:
        scheduler.shutdown(wait=False)
        await close_redis()
        logger.info("scheduler down")


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
