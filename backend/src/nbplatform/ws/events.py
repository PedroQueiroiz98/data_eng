"""Eventos de execução via Redis pub/sub (fan-out para WebSockets)."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Literal

from redis.asyncio import Redis

from nbplatform.core.config import get_settings

EventType = Literal["status_changed", "log", "output", "progress"]


def make_event(event_type: EventType, **data: Any) -> dict[str, Any]:
    return {"type": event_type, **data}


async def publish_execution_event(
    redis: Redis, execution_id: str, event: dict[str, Any]
) -> None:
    channel = get_settings().exec_event_channel(execution_id)
    await redis.publish(channel, json.dumps(event, default=str))


@asynccontextmanager
async def subscribe_execution_events(
    redis: Redis, execution_id: str
) -> AsyncIterator[AsyncIterator[dict[str, Any]]]:
    """Context manager que entrega um iterador de eventos do canal da execução."""
    channel = get_settings().exec_event_channel(execution_id)
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
