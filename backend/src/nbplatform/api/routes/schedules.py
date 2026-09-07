"""Endpoints de Schedule (cron → cria Job)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, status

from nbplatform.api.deps import SessionDep
from nbplatform.schemas.schedule import ScheduleCreate, ScheduleRead, ScheduleUpdate
from nbplatform.services.schedule_service import ScheduleService

router = APIRouter(prefix="/api/schedules", tags=["schedules"])


@router.get("", response_model=list[ScheduleRead])
async def list_schedules(
    session: SessionDep,
    workflow_id: uuid.UUID | None = Query(default=None),
) -> list[ScheduleRead]:
    schedules = await ScheduleService(session).list_schedules(workflow_id=workflow_id)
    return [ScheduleRead.model_validate(s) for s in schedules]


@router.post("", response_model=ScheduleRead, status_code=status.HTTP_201_CREATED)
async def create_schedule(payload: ScheduleCreate, session: SessionDep) -> ScheduleRead:
    schedule = await ScheduleService(session).create(
        workflow_id=payload.workflow_id,
        cron=payload.cron,
        timezone=payload.timezone,
        enabled=payload.enabled,
        parameters=payload.parameters,
    )
    await session.flush()
    return ScheduleRead.model_validate(schedule)


@router.get("/{schedule_id}", response_model=ScheduleRead)
async def get_schedule(schedule_id: uuid.UUID, session: SessionDep) -> ScheduleRead:
    return ScheduleRead.model_validate(await ScheduleService(session).get(schedule_id))


@router.put("/{schedule_id}", response_model=ScheduleRead)
async def update_schedule(
    schedule_id: uuid.UUID, payload: ScheduleUpdate, session: SessionDep
) -> ScheduleRead:
    schedule = await ScheduleService(session).update(
        schedule_id,
        cron=payload.cron,
        timezone=payload.timezone,
        enabled=payload.enabled,
        parameters=payload.parameters,
    )
    return ScheduleRead.model_validate(schedule)


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule(schedule_id: uuid.UUID, session: SessionDep) -> None:
    await ScheduleService(session).delete(schedule_id)
