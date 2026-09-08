"""Cliente Redis compartilhado + helpers de heartbeat de serviço.

A fila propriamente dita (enqueue/lease/ack/DLQ) chega na Fase 3; aqui ficam a
conexão e o registro de heartbeat consumido por `GET /ready`.
"""

from __future__ import annotations

import time

import redis.asyncio as redis

from nbplatform.core.config import get_settings

_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.from_url(get_settings().redis_url, encoding="utf-8", decode_responses=True)
    return _client


async def close_redis() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
    _client = None


async def ping() -> bool:
    try:
        return bool(await get_redis().ping())
    except Exception:
        return False


async def write_heartbeat(service: str, *, ttl_s: int) -> None:
    """Publica o heartbeat de um serviço (worker/scheduler) com TTL."""
    settings = get_settings()
    await get_redis().set(settings.heartbeat_key(service), str(time.time()), ex=ttl_s)


async def heartbeat_age_s(service: str) -> float | None:
    """Idade em segundos do último heartbeat, ou None se ausente/expirado."""
    settings = get_settings()
    raw = await get_redis().get(settings.heartbeat_key(service))
    if raw is None:
        return None
    try:
        return max(0.0, time.time() - float(raw))
    except ValueError:
        return None
