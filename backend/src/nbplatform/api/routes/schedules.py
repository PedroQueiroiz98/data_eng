"""Endpoints de Schedule (cron → cria Job). Isolados por dono do Workflow."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, status

from nbplatform.api.deps import CurrentUser, SessionDep
from nbplatform.schemas.schedule import ScheduleCreate, ScheduleRead, ScheduleUpdate
from nbplatform.services.schedule_service import ScheduleService
from nbplatform.services.workflow_service import WorkflowService

router = APIRouter(prefix="/api/schedules", tags=["schedules"])


def _is_admin(user: CurrentUser) -> bool:
    return user.role == "admin"


async def _assert_workflow_owner(
    session: SessionDep, workflow_id: uuid.UUID, user: CurrentUser
) -> None:
    await WorkflowService(session).get_owned(
        workflow_id, user_id=user.id, is_admin=_is_admin(user)
    )


@router.get("", response_model=list[ScheduleRead])
async def list_schedules(
    session: SessionDep,
    user: CurrentUser,
    workflow_id: uuid.UUID | None = Query(default=None),
) -> list[ScheduleRead]:
    owner = None if _is_admin(user) else user.id
    schedules = await ScheduleService(session).list_schedules(
        workflow_id=workflow_id, owner_id=owner
    )
    return [ScheduleRead.model_validate(s) for s in schedules]


@router.post("", response_model=ScheduleRead, status_code=status.HTTP_201_CREATED)
async def create_schedule(
    payload: ScheduleCreate, session: SessionDep, user: CurrentUser
) -> ScheduleRead:
    await _assert_workflow_owner(session, payload.workflow_id, user)
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
async def get_schedule(
    schedule_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> ScheduleRead:
    sched = await ScheduleService(session).get(schedule_id)
    await _assert_workflow_owner(session, sched.workflow_id, user)
    return ScheduleRead.model_validate(sched)


@router.put("/{schedule_id}", response_model=ScheduleRead)
async def update_schedule(
    schedule_id: uuid.UUID,
    payload: ScheduleUpdate,
    session: SessionDep,
    user: CurrentUser,
) -> ScheduleRead:
    sched = await ScheduleService(session).get(schedule_id)
    await _assert_workflow_owner(session, sched.workflow_id, user)
    schedule = await ScheduleService(session).update(
        schedule_id,
        cron=payload.cron,
        timezone=payload.timezone,
        enabled=payload.enabled,
        parameters=payload.parameters,
    )
    return ScheduleRead.model_validate(schedule)


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule(
    schedule_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> None:
    sched = await ScheduleService(session).get(schedule_id)
    await _assert_workflow_owner(session, sched.workflow_id, user)
    await ScheduleService(session).delete(schedule_id)
