"""Métricas no formato de exposição do Prometheus (text/plain 0.0.4).

Calculadas sob demanda a partir do Postgres/Redis — sem estado em processo, sem
dependência extra. `/metrics` chama `collect_snapshot` e depois `render`.
"""

from __future__ import annotations

import time
from typing import Literal

from redis.asyncio import Redis
from sqlalchemy import ColumnElement, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from nbplatform.core.config import get_settings
from nbplatform.domain.enums import ExecutionStatus, JobStatus
from nbplatform.models.execution import Execution
from nbplatform.models.job import Job

MetricType = Literal["counter", "gauge"]

_SPECS: list[tuple[str, MetricType, str]] = [
    ("nbp_executions_total", "counter", "Total de execuções criadas"),
    ("nbp_executions_success_total", "counter", "Execuções concluídas com sucesso"),
    ("nbp_executions_failed_total", "counter", "Execuções FAILED ou TIMEOUT"),
    ("nbp_executions_running", "gauge", "Execuções em RUNNING agora"),
    ("nbp_executions_queued", "gauge", "Execuções em QUEUED agora"),
    ("nbp_execution_duration_seconds_sum", "counter", "Soma das durações de execução (s)"),
    ("nbp_execution_duration_seconds_count", "counter", "Número de execuções finalizadas"),
    ("nbp_jobs_total", "counter", "Total de jobs criados"),
    ("nbp_jobs_success_total", "counter", "Jobs concluídos com sucesso"),
    ("nbp_jobs_failed_total", "counter", "Jobs FAILED"),
    ("nbp_jobs_running", "gauge", "Jobs em RUNNING agora"),
    ("nbp_jobs_queued", "gauge", "Jobs em QUEUED agora"),
    ("nbp_queue_size", "gauge", "Itens na fila de execuções (principal + atrasada)"),
    ("nbp_dlq_size", "gauge", "Itens na dead-letter queue"),
    ("nbp_worker_active", "gauge", "Workers com heartbeat dentro do lease"),
    ("nbp_scheduler_active", "gauge", "Schedulers com heartbeat dentro do lease"),
]


async def _count(
    session: AsyncSession, model: type, *where: ColumnElement[bool]
) -> int:
    stmt = select(func.count()).select_from(model)
    for clause in where:
        stmt = stmt.where(clause)
    return int(await session.scalar(stmt) or 0)


async def _heartbeat_active(redis: Redis, service: str) -> int:
    settings = get_settings()
    raw = await redis.get(settings.heartbeat_key(service))
    if raw is None:
        return 0
    try:
        age = time.time() - float(raw)
    except (TypeError, ValueError):
        return 0
    return 1 if age <= settings.worker_lease_timeout_s else 0


async def collect_snapshot(session: AsyncSession, redis: Redis) -> dict[str, float]:
    settings = get_settings()
    E, J = Execution, Job

    dur = await session.execute(
        select(
            func.coalesce(func.sum(E.duration_ms), 0),
            func.count().filter(E.finished_at.isnot(None)),
        )
    )
    dur_sum_ms, dur_count = dur.one()

    queue_main = int(await redis.llen(settings.redis_queue_executions))
    queue_delayed = int(await redis.zcard(settings.redis_queue_executions_delayed))

    return {
        "nbp_executions_total": await _count(session, E),
        "nbp_executions_success_total": await _count(
            session, E, E.status == ExecutionStatus.SUCCESS
        ),
        "nbp_executions_failed_total": await _count(
            session,
            E,
            E.status.in_([ExecutionStatus.FAILED, ExecutionStatus.TIMEOUT]),
        ),
        "nbp_executions_running": await _count(
            session, E, E.status == ExecutionStatus.RUNNING
        ),
        "nbp_executions_queued": await _count(
            session, E, E.status == ExecutionStatus.QUEUED
        ),
        "nbp_execution_duration_seconds_sum": float(dur_sum_ms or 0) / 1000.0,
        "nbp_execution_duration_seconds_count": int(dur_count or 0),
        "nbp_jobs_total": await _count(session, J),
        "nbp_jobs_success_total": await _count(session, J, J.status == JobStatus.SUCCESS),
        "nbp_jobs_failed_total": await _count(session, J, J.status == JobStatus.FAILED),
        "nbp_jobs_running": await _count(session, J, J.status == JobStatus.RUNNING),
        "nbp_jobs_queued": await _count(session, J, J.status == JobStatus.QUEUED),
        "nbp_queue_size": queue_main + queue_delayed,
        "nbp_dlq_size": int(await redis.llen(settings.redis_dlq_executions)),
        "nbp_worker_active": await _heartbeat_active(redis, "worker"),
        "nbp_scheduler_active": await _heartbeat_active(redis, "scheduler"),
    }


def render(snapshot: dict[str, float]) -> str:
    lines: list[str] = []
    for name, mtype, help_text in _SPECS:
        value = snapshot.get(name, 0)
        lines.append(f"# HELP {name} {help_text}")
        lines.append(f"# TYPE {name} {mtype}")
        rendered = int(value) if float(value).is_integer() else value
        lines.append(f"{name} {rendered}")
    return "\n".join(lines) + "\n"
