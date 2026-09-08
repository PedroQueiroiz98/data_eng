"""Endpoints de Execution (consulta, cancel/retry/delete, logs, output).

O disparo de execução vem do Workspace (`POST /api/workspaces/{id}/execute`) ou de
Jobs/Workflows — o antigo `POST /api/notebooks/{id}/execute` foi removido junto com
o módulo global de notebooks.
"""

from __future__ import annotations

import contextlib
import uuid

from fastapi import APIRouter, Query, Response, status

from nbplatform.api.deps import CurrentUserId, RedisDep, SessionDep
from nbplatform.core.config import get_settings
from nbplatform.core.errors import ConflictError
from nbplatform.domain.enums import ExecutionStatus
from nbplatform.domain.state_machine import TERMINAL_EXECUTION_STATES
from nbplatform.queue.execution_queue import ExecutionQueue
from nbplatform.schemas.execution import (
    ExecutionDetail,
    ExecutionLogRead,
    ExecutionRead,
)
from nbplatform.services.audit_service import AuditService
from nbplatform.services.execution_service import ExecutionService
from nbplatform.ws.events import make_event, publish_execution_event

router = APIRouter(tags=["executions"])


def _detail(execution: object) -> ExecutionDetail:
    detail = ExecutionDetail.model_validate(execution)
    detail.has_output = getattr(execution, "output_notebook", None) is not None
    return detail


@router.post("/api/executions/{execution_id}/cancel", response_model=ExecutionRead)
async def cancel_execution(
    execution_id: uuid.UUID, session: SessionDep, redis: RedisDep
) -> ExecutionRead:
    service = ExecutionService(session)
    execution = await service.get(execution_id)  # 404

    if execution.status in TERMINAL_EXECUTION_STATES:
        return ExecutionRead.model_validate(execution)

    if execution.status == ExecutionStatus.QUEUED:
        updated, _ = await service.cancel(execution_id)
        await session.commit()
        await publish_execution_event(
            redis,
            str(execution_id),
            make_event("status_changed", status=ExecutionStatus.CANCELLED),
        )
        return ExecutionRead.model_validate(updated)

    # RUNNING: sinaliza; o worker termina o processo e transiciona para CANCELLED.
    await ExecutionQueue(redis).request_cancel(str(execution_id))
    return ExecutionRead.model_validate(execution)


@router.post("/api/executions/{execution_id}/retry", response_model=ExecutionRead)
async def retry_execution(
    execution_id: uuid.UUID, session: SessionDep, redis: RedisDep
) -> ExecutionRead:
    service = ExecutionService(session)
    execution = await service.get(execution_id)
    if execution.status not in {ExecutionStatus.FAILED, ExecutionStatus.TIMEOUT}:
        raise ConflictError(
            f"Só é possível refazer execuções FAILED ou TIMEOUT (atual: {execution.status}). "
            "Para reexecutar uma execução cancelada, dispare o notebook novamente."
        )
    updated = await service.requeue_for_retry(execution_id)
    await session.commit()
    await ExecutionQueue(redis).enqueue(str(execution_id), attempt=updated.attempt)
    await publish_execution_event(
        redis,
        str(execution_id),
        make_event("status_changed", status=ExecutionStatus.QUEUED, attempt=updated.attempt),
    )
    return ExecutionRead.model_validate(updated)


@router.get("/api/executions", response_model=list[ExecutionRead])
async def list_executions(
    session: SessionDep,
    status_filter: ExecutionStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[ExecutionRead]:
    executions = await ExecutionService(session).list_executions(
        limit=limit, offset=offset, status=status_filter
    )
    return [ExecutionRead.model_validate(e) for e in executions]


@router.get("/api/executions/{execution_id}", response_model=ExecutionDetail)
async def get_execution(execution_id: uuid.UUID, session: SessionDep) -> ExecutionDetail:
    return _detail(await ExecutionService(session).get(execution_id))


@router.delete("/api/executions/{execution_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_execution(
    execution_id: uuid.UUID, session: SessionDep, redis: RedisDep, user_id: CurrentUserId
) -> None:
    settings = get_settings()
    service = ExecutionService(session)
    # QUEUED/RUNNING: cancela e espera encerrar antes de excluir
    await service.cancel_for_delete(
        execution_id, redis, wait_s=settings.execution_delete_cancel_wait_s
    )
    await service.delete(execution_id)
    with contextlib.suppress(Exception):
        await redis.delete(
            settings.cancel_key(str(execution_id)),
            settings.exec_seq_key(str(execution_id)),
        )
    await AuditService(session).record(
        user_id=user_id,
        action="DELETE_EXECUTION",
        resource_type="execution",
        resource_id=str(execution_id),
    )


@router.get("/api/executions/{execution_id}/logs", response_model=list[ExecutionLogRead])
async def get_execution_logs(
    execution_id: uuid.UUID,
    session: SessionDep,
    after_seq: int = Query(default=0, ge=0),
) -> list[ExecutionLogRead]:
    service = ExecutionService(session)
    await service.get(execution_id)  # 404 se não existir
    logs = await service.logs_since(execution_id, after_seq=after_seq)
    return [ExecutionLogRead.model_validate(log) for log in logs]


@router.get("/api/executions/{execution_id}/output")
async def get_execution_output(
    execution_id: uuid.UUID, session: SessionDep, response: Response
) -> dict[str, object]:
    execution = await ExecutionService(session).get(execution_id)
    if execution.output_notebook is None:
        response.status_code = status.HTTP_404_NOT_FOUND
        return {"error": {"code": "not_found", "message": "Output ainda não disponível."}}
    return execution.output_notebook
