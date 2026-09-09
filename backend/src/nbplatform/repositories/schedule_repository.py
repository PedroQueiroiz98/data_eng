"""Acesso a dados para Schedule."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nbplatform.models.schedule import Schedule


class ScheduleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, schedule: Schedule) -> None:
        self.session.add(schedule)
        await self.session.flush()

    async def get(self, schedule_id: uuid.UUID) -> Schedule | None:
        return await self.session.get(Schedule, schedule_id)

    async def get_for_update(self, schedule_id: uuid.UUID) -> Schedule | None:
        stmt = select(Schedule).where(Schedule.id == schedule_id).with_for_update()
        return await self.session.scalar(stmt)

    async def list_all(
        self,
        *,
        workflow_id: uuid.UUID | None = None,
        owner_id: uuid.UUID | None = None,
    ) -> list[Schedule]:
        stmt = select(Schedule).order_by(Schedule.created_at.desc())
        if workflow_id is not None:
            stmt = stmt.where(Schedule.workflow_id == workflow_id)
        if owner_id is not None:
            from nbplatform.models.workflow import Workflow

            stmt = stmt.join(Workflow, Workflow.id == Schedule.workflow_id).where(
                (Workflow.owner_id == owner_id) | (Workflow.owner_id.is_(None))
            )
        return list(await self.session.scalars(stmt))

    async def list_enabled(self) -> list[Schedule]:
        stmt = select(Schedule).where(Schedule.enabled.is_(True))
        return list(await self.session.scalars(stmt))

    async def delete(self, schedule: Schedule) -> None:
        await self.session.delete(schedule)
