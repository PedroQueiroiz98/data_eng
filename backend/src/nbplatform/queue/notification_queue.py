"""Fila Redis de notificações (mesma mecânica da fila de execuções).

- enqueue: LPUSH; lease: BLMOVE principal -> processing; ack: LREM
- retry com backoff: ZSET atrasada + promote_due
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import cast

from redis.asyncio import Redis

from nbplatform.core.config import get_settings


@dataclass(frozen=True)
class NotificationQueueMessage:
    notification_id: str
    raw: str


class NotificationQueue:
    def __init__(self, redis: Redis) -> None:
        self.redis = redis
        self.settings = get_settings()

    async def enqueue(self, notification_id: str) -> None:
        await self.redis.lpush(self.settings.redis_queue_notifications, notification_id)

    async def enqueue_delayed(self, notification_id: str, *, ready_at: float) -> None:
        await self.redis.zadd(
            self.settings.redis_queue_notifications_delayed, {notification_id: ready_at}
        )

    async def promote_due(self, *, now: float | None = None) -> int:
        now = time.time() if now is None else now
        key = self.settings.redis_queue_notifications_delayed
        due = cast("list[str]", await self.redis.zrangebyscore(key, min=0, max=now))
        promoted = 0
        for raw in due:
            if await self.redis.zrem(key, raw):
                await self.redis.lpush(self.settings.redis_queue_notifications, raw)
                promoted += 1
        return promoted

    async def lease(self, *, timeout_s: float) -> NotificationQueueMessage | None:
        raw = await self.redis.blmove(
            self.settings.redis_queue_notifications,
            self.settings.redis_queue_notifications_processing,
            timeout=timeout_s,  # type: ignore[arg-type]
            src="LEFT",
            dest="RIGHT",
        )
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode()
        return NotificationQueueMessage(notification_id=raw, raw=raw)

    async def ack(self, message: NotificationQueueMessage) -> None:
        await self.redis.lrem(
            self.settings.redis_queue_notifications_processing, 1, message.raw
        )

    async def queued_count(self) -> int:
        return int(await self.redis.llen(self.settings.redis_queue_notifications))

    async def next_seq(self) -> int:
        return int(await self.redis.incr(self.settings.redis_notification_seq))
