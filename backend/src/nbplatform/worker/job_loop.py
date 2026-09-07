"""Ciclo periódico que avança os Jobs em execução."""

from __future__ import annotations

import logging

from redis.asyncio import Redis

from nbplatform.db.session import session_scope
from nbplatform.repositories.job_repository import JobRepository
from nbplatform.services.job_orchestrator import JobOrchestrator

logger = logging.getLogger(__name__)


async def run_job_cycle(redis: Redis) -> int:
    async with session_scope() as session:
        job_ids = await JobRepository(session).running_job_ids()

    orchestrator = JobOrchestrator(redis)
    advanced = 0
    for job_id in job_ids:
        try:
            await orchestrator.sync_and_advance(job_id)
            advanced += 1
        except Exception:
            logger.exception("erro ao avançar job", extra={"job_id": str(job_id)})
    return advanced
