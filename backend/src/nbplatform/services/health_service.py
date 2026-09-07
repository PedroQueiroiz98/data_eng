"""Coleta o estado de prontidão das dependências (Postgres, Redis, Worker, Scheduler)."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text

from nbplatform.core.config import get_settings
from nbplatform.db.session import get_sessionmaker
from nbplatform.queue import redis_client


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str | None = None


@dataclass(frozen=True)
class Readiness:
    checks: list[Check]

    @property
    def ok(self) -> bool:
        return all(c.ok for c in self.checks)

    def as_dict(self) -> dict[str, object]:
        return {
            "status": "ok" if self.ok else "degraded",
            "checks": {c.name: {"ok": c.ok, "detail": c.detail} for c in self.checks},
        }


async def _check_postgres() -> Check:
    try:
        async with get_sessionmaker()() as session:
            await session.execute(text("SELECT 1"))
        return Check("postgres", True)
    except Exception as exc:  # noqa: BLE001 - queremos reportar qualquer falha
        return Check("postgres", False, str(exc))


async def _check_redis() -> Check:
    ok = await redis_client.ping()
    return Check("redis", ok, None if ok else "ping failed")


async def _check_service_heartbeat(service: str) -> Check:
    lease = get_settings().worker_lease_timeout_s
    age = await redis_client.heartbeat_age_s(service)
    if age is None:
        return Check(service, False, "sem heartbeat")
    if age > lease:
        return Check(service, False, f"heartbeat obsoleto ({age:.0f}s > {lease}s)")
    return Check(service, True, f"{age:.0f}s")


async def get_readiness() -> Readiness:
    checks = [
        await _check_postgres(),
        await _check_redis(),
        await _check_service_heartbeat("worker"),
        await _check_service_heartbeat("scheduler"),
    ]
    return Readiness(checks)
