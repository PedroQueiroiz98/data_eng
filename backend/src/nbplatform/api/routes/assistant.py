"""Endpoints do assistente de IA: providers (admin) + tarefas (generate/explain/...)."""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Query, status
from fastapi.responses import StreamingResponse

from nbplatform.api.deps import AdminUser, CurrentUser, RedisDep, SessionDep
from nbplatform.domain.assistant import AssistantTask
from nbplatform.queue.redis_client import get_redis
from nbplatform.repositories.assistant_repository import AssistantRepository
from nbplatform.schemas.assistant import (
    AssistantAvailability,
    AssistantInteractionPage,
    AssistantInteractionRead,
    AssistantProviderCreate,
    AssistantProviderEnabledPatch,
    AssistantProviderRead,
    AssistantProviderUpdate,
    AssistantRunRequest,
    AssistantRunResponse,
    AssistantTestResult,
    InlineCompleteRequest,
    InlineCompleteResponse,
)
from nbplatform.services.assistant import AssistantService
from nbplatform.services.assistant.provider_admin import (
    create_provider,
    delete_provider,
    get_provider,
    list_providers,
    set_enabled,
    test_provider,
    update_provider,
)
from nbplatform.services.audit_service import AuditService

router = APIRouter(prefix="/api/assistant", tags=["assistant"])


# ── providers (admin) ──────────────────────────────────────────────────────
@router.get("/providers", response_model=list[AssistantProviderRead])
async def get_providers(session: SessionDep) -> list[AssistantProviderRead]:
    return await list_providers(session)


@router.post(
    "/providers",
    response_model=AssistantProviderRead,
    status_code=status.HTTP_201_CREATED,
)
async def post_provider(
    payload: AssistantProviderCreate, session: SessionDep, admin: AdminUser
) -> AssistantProviderRead:
    result = await create_provider(session, payload)
    await AuditService(session).record(
        user_id=admin.id,
        action="CREATE_ASSISTANT_PROVIDER",
        resource_type="assistant_provider",
        resource_id=str(result.id),
        metadata={"provider_type": result.provider_type},
    )
    return result


@router.get("/providers/{provider_id}", response_model=AssistantProviderRead)
async def get_one_provider(
    provider_id: uuid.UUID, session: SessionDep
) -> AssistantProviderRead:
    return await get_provider(session, provider_id)


@router.put("/providers/{provider_id}", response_model=AssistantProviderRead)
async def put_provider(
    provider_id: uuid.UUID,
    payload: AssistantProviderUpdate,
    session: SessionDep,
    admin: AdminUser,
) -> AssistantProviderRead:
    result = await update_provider(session, provider_id, payload)
    await AuditService(session).record(
        user_id=admin.id,
        action="UPDATE_ASSISTANT_PROVIDER",
        resource_type="assistant_provider",
        resource_id=str(provider_id),
    )
    return result


@router.delete("/providers/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
async def del_provider(
    provider_id: uuid.UUID, session: SessionDep, admin: AdminUser
) -> None:
    await delete_provider(session, provider_id)
    await AuditService(session).record(
        user_id=admin.id,
        action="DELETE_ASSISTANT_PROVIDER",
        resource_type="assistant_provider",
        resource_id=str(provider_id),
    )


@router.patch("/providers/{provider_id}/enabled", response_model=AssistantProviderRead)
async def patch_provider_enabled(
    provider_id: uuid.UUID,
    payload: AssistantProviderEnabledPatch,
    session: SessionDep,
    admin: AdminUser,
) -> AssistantProviderRead:
    result = await set_enabled(session, provider_id, payload.enabled)
    await AuditService(session).record(
        user_id=admin.id,
        action="TOGGLE_ASSISTANT_PROVIDER",
        resource_type="assistant_provider",
        resource_id=str(provider_id),
        metadata={"enabled": payload.enabled},
    )
    return result


@router.post("/providers/{provider_id}/test", response_model=AssistantTestResult)
async def post_provider_test(
    provider_id: uuid.UUID, session: SessionDep, admin: AdminUser
) -> AssistantTestResult:
    result = await test_provider(session, provider_id)
    await AuditService(session).record(
        user_id=admin.id,
        action="TEST_ASSISTANT_PROVIDER",
        resource_type="assistant_provider",
        resource_id=str(provider_id),
        metadata={"ok": result.ok},
    )
    return result


# ── disponibilidade ───────────────────────────────────────────────────────
@router.get("/availability", response_model=AssistantAvailability)
async def availability(session: SessionDep, user: CurrentUser) -> AssistantAvailability:
    data = await AssistantService(session, get_redis()).availability()
    return AssistantAvailability.model_validate(data)


# ── tarefas ───────────────────────────────────────────────────────────────
def _run_kwargs(req: AssistantRunRequest, user: CurrentUser) -> dict[str, object]:
    ctx = req.context
    return {
        "cells": ctx.cells,
        "active_cell_index": ctx.active_cell_index,
        "cursor_line": ctx.cursor_line,
        "cursor_column": ctx.cursor_column,
        "selection": ctx.selection,
        "recent_error": ctx.recent_error.model_dump() if ctx.recent_error else None,
        "workspace_files": ctx.workspace_files,
        "instruction": req.instruction,
        "chat_history": [m.model_dump() for m in (req.messages or [])],
        "target_language": req.target_language,
        "user_id": user.id,
        "notebook_path": ctx.notebook_path,
        "cell_id": req.cell_id,
    }


@router.post("/run", response_model=AssistantRunResponse)
async def run(
    req: AssistantRunRequest, session: SessionDep, redis: RedisDep, user: CurrentUser
) -> AssistantRunResponse:
    result = await AssistantService(session, redis).run(req.task, **_run_kwargs(req, user))
    return AssistantRunResponse(
        ok=result.ok,
        text=result.text,
        model=result.model,
        finish_reason=result.finish_reason,
        usage=result.usage,
        error=result.error,
        interaction_id=result.interaction_id,
    )


@router.post("/run/stream")
async def run_stream(
    req: AssistantRunRequest, session: SessionDep, redis: RedisDep, user: CurrentUser
) -> StreamingResponse:
    service = AssistantService(session, redis)
    kwargs = _run_kwargs(req, user)

    async def _gen() -> AsyncIterator[bytes]:
        async for frame in service.stream(req.task, **kwargs):
            yield f"data: {json.dumps(frame, default=str)}\n\n".encode()

    return StreamingResponse(
        _gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/inline", response_model=InlineCompleteResponse)
async def inline(
    req: InlineCompleteRequest, session: SessionDep, redis: RedisDep, user: CurrentUser
) -> InlineCompleteResponse:
    ctx = req.context
    completion = await AssistantService(session, redis).inline_complete(
        cells=ctx.cells,
        active_cell_index=ctx.active_cell_index,
        cursor_line=ctx.cursor_line,
        cursor_column=ctx.cursor_column,
        user_id=user.id,
        notebook_path=ctx.notebook_path,
    )
    return InlineCompleteResponse(ok=bool(completion), completion=completion)


# ── histórico ─────────────────────────────────────────────────────────────
@router.get("/interactions", response_model=AssistantInteractionPage)
async def interactions(
    session: SessionDep,
    user: CurrentUser,
    task: Annotated[AssistantTask | None, Query()] = None,
    notebook_path: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AssistantInteractionPage:
    rows, total = await AssistantRepository(session).list_interactions(
        user.id,
        task=task.value if task else None,
        notebook_path=notebook_path,
        limit=limit,
        offset=offset,
    )
    return AssistantInteractionPage(
        items=[AssistantInteractionRead.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/interactions/{interaction_id}", response_model=AssistantInteractionRead)
async def interaction_detail(
    interaction_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> AssistantInteractionRead:
    from nbplatform.core.errors import NotFoundError

    row = await AssistantRepository(session).get_interaction(interaction_id)
    if row is None or row.user_id != user.id:
        raise NotFoundError("Interação não encontrada.")
    return AssistantInteractionRead.model_validate(row)
