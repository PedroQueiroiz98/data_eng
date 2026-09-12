"""Eventos de execução/job via Redis pub/sub (fan-out para WebSockets)."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Any, Literal

from redis.asyncio import Redis

from nbplatform.core.config import get_settings

EventType = Literal["status_changed", "log", "output", "progress"]


def make_event(event_type: str, **data: Any) -> dict[str, Any]:
    return {"type": event_type, **data}


async def publish_execution_event(redis: Redis, execution_id: str, event: dict[str, Any]) -> None:
    channel = get_settings().exec_event_channel(execution_id)
    await redis.publish(channel, json.dumps(event, default=str))


async def publish_job_event(redis: Redis, job_id: str, event: dict[str, Any]) -> None:
    channel = get_settings().job_event_channel(job_id)
    await redis.publish(channel, json.dumps(event, default=str))


async def publish_kernel_event(redis: Redis, session_id: str, event: dict[str, Any]) -> None:
    channel = get_settings().kernel_event_channel(session_id)
    await redis.publish(channel, json.dumps(event, default=str))


async def publish_config_event(redis: Redis, event: dict[str, Any]) -> None:
    """Notifica processos vivos (kernel-worker) de mudanças em config global (secrets)."""
    await redis.publish(get_settings().redis_config_event_channel, json.dumps(event, default=str))


async def publish_workspace_event(
    redis: Redis, event: dict[str, Any], *, user_id: str
) -> dict[str, Any]:
    """Evento de filesystem da Home de UM usuário.

    Ganha um `seq` monotônico (por usuário) e vai para um buffer Redis (replay
    via `after_seq`) antes do fan-out pub/sub. Espelha `KernelSessionManager._emit`.
    """
    settings = get_settings()
    seq = await redis.incr(settings.workspace_seq_key(user_id))
    payload = {**event, "seq": seq}
    raw = json.dumps(payload, default=str)
    log_key = settings.workspace_log_key(user_id)
    await redis.rpush(log_key, raw)
    await redis.ltrim(log_key, -settings.workspace_event_buffer, -1)
    await redis.publish(settings.workspace_event_channel(user_id), raw)
    return payload


@asynccontextmanager
async def subscribe_channel(
    redis: Redis, channel: str
) -> AsyncIterator[AsyncIterator[dict[str, Any]]]:
    """Entrega um iterador de eventos JSON publicados no canal."""
    pubsub = redis.pubsub()
    await pubsub.subscribe(channel)

    async def _iter() -> AsyncIterator[dict[str, Any]]:
        async for message in pubsub.listen():
            if message.get("type") != "message":
                continue
            payload = message["data"]
            if isinstance(payload, bytes):
                payload = payload.decode()
            yield json.loads(payload)

    try:
        yield _iter()
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()


_Sub = AbstractAsyncContextManager[AsyncIterator[dict[str, Any]]]


def subscribe_execution_events(redis: Redis, execution_id: str) -> _Sub:
    return subscribe_channel(redis, get_settings().exec_event_channel(execution_id))


def subscribe_job_events(redis: Redis, job_id: str) -> _Sub:
    return subscribe_channel(redis, get_settings().job_event_channel(job_id))


def subscribe_kernel_events(redis: Redis, session_id: str) -> _Sub:
    return subscribe_channel(redis, get_settings().kernel_event_channel(session_id))


def subscribe_workspace_events(redis: Redis, user_id: str) -> _Sub:
    return subscribe_channel(redis, get_settings().workspace_event_channel(user_id))


def subscribe_config_events(redis: Redis) -> _Sub:
    return subscribe_channel(redis, get_settings().redis_config_event_channel)
