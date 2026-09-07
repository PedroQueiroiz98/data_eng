"""Loop do worker que despacha notificações pendentes da fila Redis."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import uuid

from redis.asyncio import Redis

from nbplatform.queue.notification_queue import NotificationQueue
from nbplatform.services.notifications.service import NotificationService

logger = logging.getLogger(__name__)

LEASE_POLL_TIMEOUT_S = 2.0


async def run_notification_loop(stop: asyncio.Event, redis: Redis) -> None:
    queue = NotificationQueue(redis)
    service = NotificationService(redis)
    while not stop.is_set():
        with contextlib.suppress(Exception):
            await queue.promote_due()

        try:
            message = await queue.lease(timeout_s=LEASE_POLL_TIMEOUT_S)
        except Exception:
            logger.exception("erro no lease da fila de notificações")
            await asyncio.sleep(1)
            continue
        if message is None:
            continue

        try:
            await service.dispatch(uuid.UUID(message.notification_id))
        except Exception:
            logger.exception(
                "erro ao despachar notificação",
                extra={"notification_id": message.notification_id},
            )
        finally:
            await queue.ack(message)
