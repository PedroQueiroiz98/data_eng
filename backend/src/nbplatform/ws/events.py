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
