"""Dispara um schedule: cria um Job para o workflow. NUNCA executa Papermill."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta

from redis.asyncio import Redis

from nbplatform.db.session import session_scope
from nbplatform.domain.enums import TriggerType
from nbplatform.domain.schedule_spec import next_run_after
from nbplatform.repositories.schedule_repository import ScheduleRepository
from nbplatform.services.job_orchestrator import JobOrchestrator

logger = logging.getLogger(__name__)

# Evita disparo duplicado se dois ticks caírem quase juntos.
_MIN_INTERVAL_S = 5


async def run_due_schedule(schedule_id: str, redis: Redis) -> uuid.UUID | None:
    sched_uuid = uuid.UUID(schedule_id)
    now = datetime.now(UTC)

    async with session_scope() as session:
        repo = ScheduleRepository(session)
        schedule = await repo.get_for_update(sched_uuid)
        if schedule is None or not schedule.enabled:
            return None
        if schedule.last_run_at is not None and now - schedule.last_run_at < timedelta(
            seconds=_MIN_INTERVAL_S
        ):
            return None

        workflow_id = schedule.workflow_id
        parameters = dict(schedule.parameters or {})
        schedule.last_run_at = now
        schedule.next_run_at = next_run_after(schedule.cron, schedule.timezone, after=now)

    try:
        job_id = await JobOrchestrator(redis).start_job(
            workflow_id,
            trigger_type=TriggerType.SCHEDULED,
            created_by=None,
            parameters=parameters,
        )
    except Exception:
        logger.exception(
            "schedule disparou mas falhou ao criar Job",
            extra={"schedule_id": schedule_id},
        )
        return None

    logger.info(
        "schedule disparou",
        extra={"schedule_id": schedule_id, "job_id": str(job_id)},
    )
    return job_id
