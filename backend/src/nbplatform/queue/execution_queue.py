"""Fila de execuções sobre Redis.

- enqueue: LPUSH na lista principal
- lease:   BLMOVE principal -> processing (visibilidade em caso de crash do worker)
- ack:     LREM do payload da lista processing
- dlq:     LPUSH na lista de dead-letter (usado na Fase 4)

O payload é um JSON `{"execution_id": ..., "attempt": ..., "enqueued_at": ...}`.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass

from redis.asyncio import Redis

from nbplatform.core.config import get_settings


@dataclass(frozen=True)
class QueueMessage:
    execution_id: str
    attempt: int
    raw: str

    @classmethod
    def decode(cls, raw: str) -> QueueMessage:
        data = json.loads(raw)
        return cls(
            execution_id=str(data["execution_id"]),
            attempt=int(data.get("attempt", 1)),
            raw=raw,
        )


def _encode(execution_id: str, attempt: int) -> str:
    return json.dumps(
        {"execution_id": execution_id, "attempt": attempt, "enqueued_at": time.time()}
    )


class ExecutionQueue:
    def __init__(self, redis: Redis) -> None:
        self.redis = redis
        self.settings = get_settings()

    async def enqueue(self, execution_id: str, *, attempt: int = 1) -> None:
        await self.redis.lpush(self.settings.redis_queue_executions, _encode(execution_id, attempt))

    async def lease(self, *, timeout_s: float) -> QueueMessage | None:
        raw = await self.redis.blmove(
            self.settings.redis_queue_executions,
            self.settings.redis_queue_executions_processing,
            timeout=timeout_s,  # type: ignore[arg-type]  # Redis aceita float
            src="LEFT",
            dest="RIGHT",
        )
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode()
        return QueueMessage.decode(raw)

    async def ack(self, message: QueueMessage) -> None:
        await self.redis.lrem(self.settings.redis_queue_executions_processing, 1, message.raw)

    async def to_dlq(self, message: QueueMessage, *, reason: str) -> None:
        await self.ack(message)
        payload = json.dumps(
            {"execution_id": message.execution_id, "attempt": message.attempt, "reason": reason}
        )
        await self.redis.lpush(self.settings.redis_dlq_executions, payload)

    async def queued_count(self) -> int:
        return int(await self.redis.llen(self.settings.redis_queue_executions))

    async def next_seq(self, execution_id: str) -> int:
        return int(await self.redis.incr(self.settings.exec_seq_key(execution_id)))
