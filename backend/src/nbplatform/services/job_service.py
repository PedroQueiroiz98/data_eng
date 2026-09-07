"""Consulta e controle de Jobs (create fica no JobOrchestrator)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nbplatform.core.errors import ConflictError, NotFoundError
from nbplatform.core.masking import mask_params
from nbplatform.domain.enums import JobStatus, JobTaskStatus
from nbplatform.domain.job_state import JOB_TERMINAL
from nbplatform.models.job import Job, JobLog
from nbplatform.models.notebook import Notebook
from nbplatform.models.user import User
from nbplatform.repositories.job_repository import JobRepository
from nbplatform.repositories.workflow_repository import WorkflowRepository
from nbplatform.schemas.job import JobDetail, JobTaskRead

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

    async def detail(self, job_id: uuid.UUID) -> JobDetail:
        """Job + tarefas (com nome/notebook) + dependências + parâmetros mascarados."""
        job = await self.get(job_id)
        wf = await WorkflowRepository(self.session).get_with_graph(job.workflow_id)
        wtasks = wf.tasks if wf else []
        name_by_wtid = {t.id: t.name for t in wtasks}
        nb_by_wtid = {t.id: t.notebook_id for t in wtasks}

        nb_ids = {nid for nid in nb_by_wtid.values() if nid is not None}
        nb_name: dict[uuid.UUID, str] = {}
        if nb_ids:
            rows = await self.session.execute(
                select(Notebook.id, Notebook.name).where(Notebook.id.in_(nb_ids))
            )
            nb_name = {row[0]: row[1] for row in rows.all()}

        detail = JobDetail.model_validate(job)
        detail.workflow_name = wf.name if wf else ""
        detail.parameters = mask_params(job.parameters or {})
        if job.created_by is not None:
            user = await self.session.get(User, job.created_by)
            detail.started_by = user.email if user else None

        detail.tasks = []
        for jt in sorted(job.tasks, key=lambda t: name_by_wtid.get(t.workflow_task_id, "")):
            item = JobTaskRead.model_validate(jt)
            item.name = name_by_wtid.get(jt.workflow_task_id, "")
            nb_id = nb_by_wtid.get(jt.workflow_task_id)
            item.notebook_id = nb_id
            item.notebook_name = nb_name.get(nb_id, "") if nb_id else ""
            detail.tasks.append(item)

        detail.dependencies = [
            {"from": str(d.from_task_id), "to": str(d.to_task_id)}
            for d in (wf.dependencies if wf else [])
        ]
        return detail

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
