"""Endpoints de Job: disparo a partir de um Workflow, consulta e controle."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, status

from nbplatform.api.deps import CurrentUserId, RedisDep, SessionDep
from nbplatform.core.config import get_settings
from nbplatform.core.errors import ConflictError
from nbplatform.db.session import session_scope
from nbplatform.domain.enums import JobStatus, TriggerType
from nbplatform.domain.job_state import JOB_TERMINAL
from nbplatform.repositories.workflow_repository import WorkflowRepository
from nbplatform.schemas.job import JobDetail, JobLogRead, JobRead, JobRunRequest, JobTaskRead
from nbplatform.services.audit_service import AuditService
from nbplatform.services.job_orchestrator import JobOrchestrator
from nbplatform.services.job_service import JobService
from nbplatform.ws.events import make_event, publish_job_event

router = APIRouter(tags=["jobs"])


async def _detail(session: SessionDep, job_id: uuid.UUID) -> JobDetail:
    service = JobService(session)
    job = await service.get(job_id)
    wf = await WorkflowRepository(session).get_with_graph(job.workflow_id)
    name_by_wtid = {t.id: t.name for t in (wf.tasks if wf else [])}

    detail = JobDetail.model_validate(job)
    detail.workflow_name = wf.name if wf else ""
    detail.tasks = []
    for jt in sorted(job.tasks, key=lambda t: name_by_wtid.get(t.workflow_task_id, "")):
        item = JobTaskRead.model_validate(jt)
        item.name = name_by_wtid.get(jt.workflow_task_id, "")
        detail.tasks.append(item)
    detail.dependencies = [
        {"from": str(d.from_task_id), "to": str(d.to_task_id)}
        for d in (wf.dependencies if wf else [])
    ]
    return detail


@router.post(
    "/api/workflows/{workflow_id}/run",
    response_model=JobRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def run_workflow(
    workflow_id: uuid.UUID,
    payload: JobRunRequest,
    session: SessionDep,
    redis: RedisDep,
    user_id: CurrentUserId,
) -> JobRead:
    job_id = await JobOrchestrator(redis).start_job(
        workflow_id,
        trigger_type=TriggerType.MANUAL,
        created_by=user_id,
        parameters=payload.parameters,
    )
    async with session_scope() as audit_session:
        await AuditService(audit_session).record(
            user_id=user_id,
            action="RUN_WORKFLOW",
            resource_type="job",
            resource_id=str(job_id),
            metadata={"workflow_id": str(workflow_id)},
        )
    return JobRead.model_validate(await JobService(session).get(job_id))


@router.get("/api/jobs", response_model=list[JobRead])
async def list_jobs(
    session: SessionDep,
    workflow_id: uuid.UUID | None = Query(default=None),
    status_filter: JobStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[JobRead]:
    jobs = await JobService(session).list_jobs(
        limit=limit, offset=offset, workflow_id=workflow_id, status=status_filter
    )
    return [JobRead.model_validate(j) for j in jobs]


@router.get("/api/jobs/{job_id}", response_model=JobDetail)
async def get_job(job_id: uuid.UUID, session: SessionDep) -> JobDetail:
    return await _detail(session, job_id)


@router.get("/api/jobs/{job_id}/logs", response_model=list[JobLogRead])
async def get_job_logs(
    job_id: uuid.UUID, session: SessionDep, after_seq: int = Query(default=0, ge=0)
) -> list[JobLogRead]:
    logs = await JobService(session).logs_since(job_id, after_seq=after_seq)
    return [JobLogRead.model_validate(log) for log in logs]


@router.post("/api/jobs/{job_id}/cancel", response_model=JobRead)
async def cancel_job(
    job_id: uuid.UUID, session: SessionDep, redis: RedisDep, user_id: CurrentUserId
) -> JobRead:
    service = JobService(session)
    current = await service.get_status(job_id)  # 404
    if current not in JOB_TERMINAL:
        await redis.set(
            get_settings().job_cancel_key(str(job_id)), "1", ex=3600
        )
        await AuditService(session).record(
            user_id=user_id, action="CANCEL_JOB", resource_type="job", resource_id=str(job_id)
        )
        await publish_job_event(
            redis, str(job_id), make_event("status_changed", status="CANCELLING")
        )
        await session.commit()
        await JobOrchestrator(redis).sync_and_advance(job_id)
    return JobRead.model_validate(await service.get(job_id))


@router.post("/api/jobs/{job_id}/retry", response_model=JobRead)
async def retry_job(
    job_id: uuid.UUID, session: SessionDep, redis: RedisDep
) -> JobRead:
    service = JobService(session)
    try:
        job = await service.reset_for_retry(job_id)
    except ConflictError:
        raise
    await session.commit()
    await redis.delete(get_settings().job_cancel_key(str(job_id)))
    await JobOrchestrator(redis).sync_and_advance(job_id)
    return JobRead.model_validate(await service.get(job.id))
