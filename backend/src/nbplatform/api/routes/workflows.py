"""Endpoints de Workflow (definição + grafo). Execução vira Job na Fase 6."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, status

from nbplatform.api.deps import CurrentUserId, SessionDep
from nbplatform.schemas.workflow import (
    WorkflowCreate,
    WorkflowDetail,
    WorkflowGraphSave,
    WorkflowRead,
    WorkflowUpdate,
)
from nbplatform.services.audit_service import AuditService
from nbplatform.services.workflow_service import WorkflowService

router = APIRouter(prefix="/api/workflows", tags=["workflows"])


@router.get("", response_model=list[WorkflowRead])
async def list_workflows(
    session: SessionDep,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[WorkflowRead]:
    workflows = await WorkflowService(session).list_workflows(limit=limit, offset=offset)
    return [WorkflowRead.model_validate(w) for w in workflows]


@router.post("", response_model=WorkflowDetail, status_code=status.HTTP_201_CREATED)
async def create_workflow(
    payload: WorkflowCreate, session: SessionDep, user_id: CurrentUserId
) -> WorkflowDetail:
    service = WorkflowService(session)
    workflow = await service.create(name=payload.name, description=payload.description)
    await session.flush()
    await AuditService(session).record(
        user_id=user_id,
        action="CREATE_WORKFLOW",
        resource_type="workflow",
        resource_id=str(workflow.id),
        metadata={"name": workflow.name},
    )
    return WorkflowDetail.model_validate(await service.get(workflow.id))


@router.get("/{workflow_id}", response_model=WorkflowDetail)
async def get_workflow(workflow_id: uuid.UUID, session: SessionDep) -> WorkflowDetail:
    return WorkflowDetail.model_validate(await WorkflowService(session).get(workflow_id))


@router.put("/{workflow_id}", response_model=WorkflowDetail)
async def update_workflow(
    workflow_id: uuid.UUID, payload: WorkflowUpdate, session: SessionDep
) -> WorkflowDetail:
    service = WorkflowService(session)
    await service.update_metadata(
        workflow_id,
        name=payload.name,
        description=payload.description,
        status=payload.status,
    )
    return WorkflowDetail.model_validate(await service.get(workflow_id))


@router.delete("/{workflow_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workflow(workflow_id: uuid.UUID, session: SessionDep) -> None:
    await WorkflowService(session).delete(workflow_id)


@router.put("/{workflow_id}/graph", response_model=WorkflowDetail)
async def save_graph(
    workflow_id: uuid.UUID, payload: WorkflowGraphSave, session: SessionDep
) -> WorkflowDetail:
    workflow = await WorkflowService(session).save_graph(
        workflow_id, tasks=payload.tasks, dependencies=payload.dependencies
    )
    return WorkflowDetail.model_validate(workflow)
