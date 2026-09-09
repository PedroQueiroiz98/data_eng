"""Acesso a dados para Job / JobTask / JobLog."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from nbplatform.domain.enums import JobStatus
from nbplatform.models.job import Job, JobLog, JobTask


class JobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, job: Job) -> None:
        self.session.add(job)
        await self.session.flush()

    async def get(self, job_id: uuid.UUID) -> Job | None:
        return await self.session.get(Job, job_id)

    async def get_with_tasks(self, job_id: uuid.UUID) -> Job | None:
        stmt = select(Job).where(Job.id == job_id).options(selectinload(Job.tasks))
        return await self.session.scalar(stmt)

    async def get_for_update(self, job_id: uuid.UUID) -> Job | None:
        stmt = select(Job).where(Job.id == job_id).with_for_update()
        return await self.session.scalar(stmt)

    async def list_paged(
        self,
        *,
        limit: int,
        offset: int,
        workflow_id: uuid.UUID | None = None,
        status: JobStatus | None = None,
        created_by: uuid.UUID | None = None,
    ) -> list[Job]:
        stmt = select(Job).order_by(Job.created_at.desc()).options(selectinload(Job.tasks))
        if workflow_id is not None:
            stmt = stmt.where(Job.workflow_id == workflow_id)
        if status is not None:
            stmt = stmt.where(Job.status == status)
        if created_by is not None:
            stmt = stmt.where(Job.created_by == created_by)
        stmt = stmt.limit(limit).offset(offset)
        return list(await self.session.scalars(stmt))

    async def running_job_ids(self) -> list[uuid.UUID]:
        stmt = select(Job.id).where(Job.status == JobStatus.RUNNING)
        return list(await self.session.scalars(stmt))

    async def lock_if_running(self, job_id: uuid.UUID) -> Job | None:
        stmt = (
            select(Job)
            .where(Job.id == job_id, Job.status == JobStatus.RUNNING)
            .with_for_update(skip_locked=True)
        )
        return await self.session.scalar(stmt)

    async def tasks_for(self, job_id: uuid.UUID) -> list[JobTask]:
        stmt = select(JobTask).where(JobTask.job_id == job_id)
        return list(await self.session.scalars(stmt))

    async def add_log(self, log: JobLog) -> None:
        self.session.add(log)
        await self.session.flush()

    async def logs_since(self, job_id: uuid.UUID, *, after_seq: int = 0) -> list[JobLog]:
        stmt = (
            select(JobLog)
            .where(JobLog.job_id == job_id, JobLog.seq > after_seq)
            .order_by(JobLog.seq)
        )
        return list(await self.session.scalars(stmt))
