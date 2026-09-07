"""Consulta e controle de Jobs (create fica no JobOrchestrator)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from nbplatform.core.errors import ConflictError, NotFoundError
from nbplatform.domain.enums import JobStatus, JobTaskStatus
from nbplatform.domain.job_state import JOB_TERMINAL
from nbplatform.models.job import Job, JobLog
from nbplatform.repositories.job_repository import JobRepository

_RETRYABLE_TASK_STATES = {
    JobTaskStatus.FAILED,
    JobTaskStatus.CANCELLED,
    JobTaskStatus.SKIPPED,
}


class JobService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = JobRepository(session)

    async def get(self, job_id: uuid.UUID) -> Job:
        job = await self.repo.get_with_tasks(job_id)
        if job is None:
            raise NotFoundError(f"Job {job_id} não encontrado.")
        return job

    async def list_jobs(
        self,
        *,
        limit: int,
        offset: int,
        workflow_id: uuid.UUID | None,
        status: JobStatus | None,
    ) -> list[Job]:
        return await self.repo.list_paged(
            limit=limit, offset=offset, workflow_id=workflow_id, status=status
        )

    async def logs_since(self, job_id: uuid.UUID, *, after_seq: int) -> list[JobLog]:
        await self.get(job_id)
        return await self.repo.logs_since(job_id, after_seq=after_seq)

    async def get_status(self, job_id: uuid.UUID) -> JobStatus:
        job = await self.repo.get(job_id)
        if job is None:
            raise NotFoundError(f"Job {job_id} não encontrado.")
        return job.status

    async def reset_for_retry(self, job_id: uuid.UUID) -> Job:
        job = await self.repo.get_with_tasks(job_id)
        if job is None:
            raise NotFoundError(f"Job {job_id} não encontrado.")
        if job.status not in JOB_TERMINAL:
            raise ConflictError(
                f"Só é possível refazer um Job terminal (atual: {job.status})."
            )
        if job.status == JobStatus.SUCCESS:
            raise ConflictError("Job já concluiu com sucesso.")

        for task in job.tasks:
            if task.status in _RETRYABLE_TASK_STATES:
                task.status = JobTaskStatus.PENDING
                task.execution_id = None
                task.error_message = None
                task.started_at = None
                task.finished_at = None
                task.duration_ms = None
                task.attempt = 0

        job.status = JobStatus.RUNNING
        job.started_at = datetime.now(UTC)
        job.finished_at = None
        job.duration_ms = None
        await self.session.flush()
        return job
