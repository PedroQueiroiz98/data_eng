"""Utilitários de ciclo de vida para os processos worker/scheduler."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import signal

from nbplatform.core.config import get_settings
from nbplatform.queue.redis_client import write_heartbeat

logger = logging.getLogger(__name__)


def install_signal_handlers(loop: asyncio.AbstractEventLoop, stop: asyncio.Event) -> None:
    def _handle() -> None:
        logger.info("sinal de parada recebido")
        stop.set()

    # Windows não implementa add_signal_handler para SIGTERM.
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, _handle)


async def heartbeat_loop(service: str, stop: asyncio.Event) -> None:
    """Publica heartbeat periódico até `stop` ser sinalizado."""
    settings = get_settings()
    interval = settings.worker_heartbeat_interval_s
    ttl = max(interval * 3, settings.worker_lease_timeout_s)
    while not stop.is_set():
        try:
            await write_heartbeat(service, ttl_s=ttl)
        except Exception:  # noqa: BLE001 - heartbeat não deve derrubar o serviço
            logger.warning("falha ao publicar heartbeat", extra={"service": service})
        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=interval)
