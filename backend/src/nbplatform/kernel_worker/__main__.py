"""`python -m nbplatform.kernel_worker` — kernels Python interativos por sessão.

Espelha `nbplatform.worker.__main__`: stop event, signal handlers, heartbeat.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging

from nbplatform.core.config import get_settings
from nbplatform.core.logging import configure_logging
from nbplatform.core.runtime import heartbeat_loop, install_signal_handlers
from nbplatform.kernel.manager import KernelSessionManager
from nbplatform.queue.redis_client import close_redis, get_redis, ping

logger = logging.getLogger(__name__)


async def _run() -> None:
    settings = get_settings()
    configure_logging(settings.log_level, service="kernel")
    logger.info("kernel-worker up", extra={"enabled": settings.kernel_enabled})

    if not await ping():
        logger.error("Redis indisponível no start; encerrando para reinício pelo orquestrador")
        raise SystemExit(1)

    stop = asyncio.Event()
    install_signal_handlers(asyncio.get_running_loop(), stop)
    hb = asyncio.create_task(heartbeat_loop("kernel", stop))
    manager = KernelSessionManager(get_redis())
    try:
        if settings.kernel_enabled:
            await manager.run(stop)
        else:
            await stop.wait()
    finally:
        stop.set()
        hb.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await hb
        await close_redis()
        logger.info("kernel-worker down")


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
