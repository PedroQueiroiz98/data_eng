"""Acesso a dados para Workflow / WorkflowTask / WorkflowDependency."""

from __future__ import annotations

import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from nbplatform.models.workflow import Workflow, WorkflowDependency, WorkflowTask


class WorkflowRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, workflow: Workflow) -> None:
        self.session.add(workflow)
        await self.session.flush()

    async def get(self, workflow_id: uuid.UUID) -> Workflow | None:
        return await self.session.get(Workflow, workflow_id)

    async def get_with_graph(self, workflow_id: uuid.UUID) -> Workflow | None:
        stmt = (
            select(Workflow)
            .where(Workflow.id == workflow_id)
            .options(
                selectinload(Workflow.tasks),
                selectinload(Workflow.dependencies),
            )
        )
        return await self.session.scalar(stmt)

    async def list_paged(self, *, limit: int, offset: int) -> list[Workflow]:
        stmt = select(Workflow).order_by(Workflow.updated_at.desc()).limit(limit).offset(offset)
        return list(await self.session.scalars(stmt))

    async def delete(self, workflow: Workflow) -> None:
        await self.session.delete(workflow)

    async def tasks_for(self, workflow_id: uuid.UUID) -> list[WorkflowTask]:
        stmt = select(WorkflowTask).where(WorkflowTask.workflow_id == workflow_id)
        return list(await self.session.scalars(stmt))

    async def delete_tasks(self, workflow_id: uuid.UUID, task_ids: list[uuid.UUID]) -> None:
        if not task_ids:
            return
        await self.session.execute(delete(WorkflowTask).where(WorkflowTask.id.in_(task_ids)))

    async def clear_dependencies(self, workflow_id: uuid.UUID) -> None:
        await self.session.execute(
            delete(WorkflowDependency).where(WorkflowDependency.workflow_id == workflow_id)
        )

    async def count_tasks(self, workflow_id: uuid.UUID) -> int:
        stmt = (
            select(func.count())
            .select_from(WorkflowTask)
            .where(WorkflowTask.workflow_id == workflow_id)
        )
        return int(await self.session.scalar(stmt) or 0)
