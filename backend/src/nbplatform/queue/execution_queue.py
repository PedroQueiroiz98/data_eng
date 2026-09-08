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
from typing import cast

from redis.asyncio import Redis

from nbplatform.core.config import get_settings

CANCEL_TTL_S = 3600


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
        await self.dead_letter(message.execution_id, attempt=message.attempt, reason=reason)

    async def dead_letter(self, execution_id: str, *, attempt: int, reason: str) -> None:
        payload = json.dumps(
            {
                "execution_id": execution_id,
                "attempt": attempt,
                "reason": reason,
                "at": time.time(),
            }
        )
        await self.redis.lpush(self.settings.redis_dlq_executions, payload)

    async def dlq_size(self) -> int:
        return int(await self.redis.llen(self.settings.redis_dlq_executions))

    async def queued_count(self) -> int:
        return int(await self.redis.llen(self.settings.redis_queue_executions))

    async def next_seq(self, execution_id: str) -> int:
        return int(await self.redis.incr(self.settings.exec_seq_key(execution_id)))

    # ── retry com atraso (backoff) ───────────────────────────────────────────
    async def enqueue_delayed(self, execution_id: str, *, attempt: int, ready_at: float) -> None:
        await self.redis.zadd(
            self.settings.redis_queue_executions_delayed,
            {_encode(execution_id, attempt): ready_at},
        )

    async def promote_due(self, *, now: float | None = None) -> int:
        """Move entradas vencidas da delayed queue para a fila principal."""
        now = time.time() if now is None else now
        key = self.settings.redis_queue_executions_delayed
        due = cast("list[str]", await self.redis.zrangebyscore(key, min=0, max=now))
        promoted = 0
        for raw in due:
            if await self.redis.zrem(key, raw):  # só quem removeu promove (evita corrida)
                await self.redis.lpush(self.settings.redis_queue_executions, raw)
                promoted += 1
        return promoted

    # ── cancelamento (sinal para o worker que está executando) ───────────────
    async def request_cancel(self, execution_id: str) -> None:
        await self.redis.set(self.settings.cancel_key(execution_id), "1", ex=CANCEL_TTL_S)

    async def is_cancel_requested(self, execution_id: str) -> bool:
        return bool(await self.redis.exists(self.settings.cancel_key(execution_id)))

    async def clear_cancel(self, execution_id: str) -> None:
        await self.redis.delete(self.settings.cancel_key(execution_id))
