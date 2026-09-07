"""`python -m nbplatform.worker` — consome a fila e executa notebooks via Papermill.

Fase 3: lease via BLMOVE, execução em subprocesso, logs em tempo real, output.ipynb.
Recovery de lease expirado / retry / DLQ chegam na Fase 4.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import uuid

from redis.asyncio import Redis

from nbplatform.core.config import get_settings
from nbplatform.core.logging import configure_logging
from nbplatform.core.runtime import heartbeat_loop, install_signal_handlers
from nbplatform.queue.execution_queue import ExecutionQueue, QueueMessage
from nbplatform.queue.redis_client import close_redis, get_redis, ping
from nbplatform.worker.execution_manager import ExecutionManager, cleanup_workdir

logger = logging.getLogger(__name__)

WORKER_ID = f"worker-{uuid.uuid4().hex[:8]}"
LEASE_POLL_TIMEOUT_S = 2.0


async def _process(message: QueueMessage, redis: Redis, sem: asyncio.Semaphore) -> None:
    manager = ExecutionManager(redis, worker_id=WORKER_ID)
    try:
        status = await manager.run(message.execution_id, attempt=message.attempt)
        logger.info(
            "execução finalizada",
            extra={"execution_id": message.execution_id, "status": status},
        )
    except Exception:
        logger.exception(
            "falha inesperada ao processar execução",
            extra={"execution_id": message.execution_id},
        )
    finally:
        await ExecutionQueue(redis).ack(message)
        cleanup_workdir(message.execution_id)
        sem.release()


async def _consume_loop(stop: asyncio.Event) -> None:
    settings = get_settings()
    redis = get_redis()
    queue = ExecutionQueue(redis)
    sem = asyncio.Semaphore(settings.max_concurrent_executions)
    tasks: set[asyncio.Task[None]] = set()

    while not stop.is_set():
        await sem.acquire()
        if stop.is_set():
            sem.release()
            break
        try:
            message = await queue.lease(timeout_s=LEASE_POLL_TIMEOUT_S)
        except Exception:
            logger.exception("erro ao fazer lease da fila")
            sem.release()
            await asyncio.sleep(1)
            continue

        if message is None:
            sem.release()
            continue

        task = asyncio.create_task(_process(message, redis, sem))
        tasks.add(task)
        task.add_done_callback(tasks.discard)

    if tasks:
        logger.info("aguardando %d execuções em andamento", len(tasks))
        await asyncio.gather(*tasks, return_exceptions=True)


async def _run() -> None:
    settings = get_settings()
    configure_logging(settings.log_level, service="worker")
    logger.info(
        "worker up",
        extra={"worker_id": WORKER_ID, "max_concurrent": settings.max_concurrent_executions},
    )

    if not await ping():
        logger.error("Redis indisponível no start; encerrando para reinício pelo orquestrador")
        raise SystemExit(1)

    stop = asyncio.Event()
    install_signal_handlers(asyncio.get_running_loop(), stop)

    hb = asyncio.create_task(heartbeat_loop("worker", stop))
    consumer = asyncio.create_task(_consume_loop(stop))
    try:
        await asyncio.gather(hb, consumer)
    finally:
        stop.set()
        hb.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await hb
        await close_redis()
        logger.info("worker down", extra={"worker_id": WORKER_ID})


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
