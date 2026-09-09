"""Regras de negócio de Schedule (CRUD + validação de cron)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from nbplatform.core.errors import NotFoundError
from nbplatform.domain.schedule_spec import next_run_after, validate_cron
from nbplatform.models.schedule import Schedule
from nbplatform.repositories.schedule_repository import ScheduleRepository
from nbplatform.repositories.workflow_repository import WorkflowRepository


class ScheduleService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = ScheduleRepository(session)
        self.workflows = WorkflowRepository(session)

    async def create(
        self,
        *,
        workflow_id: uuid.UUID,
        cron: str,
        timezone: str,
        enabled: bool,
        parameters: dict[str, Any],
    ) -> Schedule:
        validate_cron(cron, timezone)
        if await self.workflows.get(workflow_id) is None:
            raise NotFoundError(f"Workflow {workflow_id} não encontrado.")

        schedule = Schedule(
            workflow_id=workflow_id,
            cron=cron,
            timezone=timezone,
            enabled=enabled,
            parameters=parameters,
            next_run_at=next_run_after(cron, timezone, after=datetime.now(UTC))
            if enabled
            else None,
        )
        await self.repo.add(schedule)
        return schedule

    async def get(self, schedule_id: uuid.UUID) -> Schedule:
        schedule = await self.repo.get(schedule_id)
        if schedule is None:
            raise NotFoundError(f"Schedule {schedule_id} não encontrado.")
        return schedule

    async def list_schedules(
        self, *, workflow_id: uuid.UUID | None, owner_id: uuid.UUID | None = None
    ) -> list[Schedule]:
        return await self.repo.list_all(workflow_id=workflow_id, owner_id=owner_id)

    async def update(
        self,
        schedule_id: uuid.UUID,
        *,
        cron: str | None,
        timezone: str | None,
        enabled: bool | None,
        parameters: dict[str, Any] | None,
    ) -> Schedule:
        schedule = await self.get(schedule_id)
        new_cron = cron if cron is not None else schedule.cron
        new_tz = timezone if timezone is not None else schedule.timezone
        validate_cron(new_cron, new_tz)

        schedule.cron = new_cron
        schedule.timezone = new_tz
        if enabled is not None:
            schedule.enabled = enabled
        if parameters is not None:
            schedule.parameters = parameters

        schedule.next_run_at = (
            next_run_after(new_cron, new_tz, after=datetime.now(UTC)) if schedule.enabled else None
        )
        await self.session.flush()
        return schedule

    async def delete(self, schedule_id: uuid.UUID) -> None:
        schedule = await self.get(schedule_id)
        await self.repo.delete(schedule)
