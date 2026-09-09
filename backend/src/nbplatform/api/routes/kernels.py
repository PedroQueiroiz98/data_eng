"""Kernel Python interativo por notebook/usuário no Workspace único (`/root`).

Interativo (edição/exploração) — não confundir com a execução de produção via
Papermill (`POST /api/workspace/execute`, Jobs, agendamentos).
"""

from __future__ import annotations

import hashlib
import json
import uuid

from fastapi import APIRouter, status

from nbplatform.api.deps import RedisDep, WorkspaceEditor
from nbplatform.core.config import get_settings
from nbplatform.core.errors import DomainValidationError, NotFoundError
from nbplatform.domain.workspace_paths import is_ipynb
from nbplatform.schemas.kernel import (
    KernelExecuteAccepted,
    KernelExecuteRequest,
    KernelSessionCreate,
    KernelSessionRead,
)
from nbplatform.services.workspace_service import SINGLETON_WORKSPACE_ID

router = APIRouter(prefix="/api/workspace/kernel", tags=["kernel"])

_WID = str(SINGLETON_WORKSPACE_ID)


def _session_id(notebook_path: str, user_id: uuid.UUID) -> str:
    raw = f"{_WID}:{notebook_path}:{user_id}".encode()
    return hashlib.sha1(raw).hexdigest()[:20]


async def _load_session(redis: RedisDep, session_id: str) -> dict[str, str]:
    meta = await redis.hgetall(get_settings().kernel_sess_key(session_id))
    if not meta:
        raise NotFoundError("Sessão de kernel não encontrada.")
    return {str(k): str(v) for k, v in meta.items()}


def _guard(meta: dict[str, str], user_id: uuid.UUID) -> None:
    if meta.get("user_id") != str(user_id):
        raise NotFoundError("Sessão de kernel não encontrada.")


async def _push_op(redis: RedisDep, op: dict[str, object]) -> None:
    await redis.rpush(get_settings().redis_kernel_ops, json.dumps(op))


@router.post("/sessions", response_model=KernelSessionRead)
async def open_session(
    payload: KernelSessionCreate,
    redis: RedisDep,
    access: WorkspaceEditor,
) -> KernelSessionRead:
    if not is_ipynb(payload.notebook_path):
        raise DomainValidationError("Sessão de kernel apenas para arquivos .ipynb.")

    settings = get_settings()
    sid = _session_id(payload.notebook_path, access.user.id)
    key = settings.kernel_sess_key(sid)
    existing = await redis.hgetall(key)
    await redis.hset(
        key,
        mapping={
            "workspace_id": _WID,
            "notebook_path": payload.notebook_path,
            "user_id": str(access.user.id),
            "status": existing.get("status", "starting"),
            "execution_count": existing.get("execution_count", "0"),
        },
    )
    await redis.expire(key, int(settings.kernel_idle_timeout_s * 2))
    await _push_op(redis, {"op": "ensure", "session_id": sid})
    return KernelSessionRead(
        session_id=sid,
        status=existing.get("status", "starting"),
        execution_count=int(existing.get("execution_count") or 0),
        notebook_path=payload.notebook_path,
    )


@router.get("/sessions/{session_id}", response_model=KernelSessionRead)
async def get_session(
    session_id: str,
    redis: RedisDep,
    access: WorkspaceEditor,
) -> KernelSessionRead:
    meta = await _load_session(redis, session_id)
    _guard(meta, access.user.id)
    return KernelSessionRead(
        session_id=session_id,
        status=meta.get("status", "starting"),
        execution_count=int(meta.get("execution_count") or 0),
        notebook_path=meta.get("notebook_path", ""),
    )


@router.post(
    "/sessions/{session_id}/execute",
    response_model=KernelExecuteAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def execute_cell(
    session_id: str,
    payload: KernelExecuteRequest,
    redis: RedisDep,
    access: WorkspaceEditor,
) -> KernelExecuteAccepted:
    meta = await _load_session(redis, session_id)
    _guard(meta, access.user.id)
    request_id = uuid.uuid4().hex
    await _push_op(
        redis,
        {
            "op": "execute",
            "session_id": session_id,
            "cell_id": payload.cell_id,
            "code": payload.code,
            "request_id": request_id,
        },
    )
    return KernelExecuteAccepted(request_id=request_id)


@router.post("/sessions/{session_id}/interrupt", status_code=status.HTTP_202_ACCEPTED)
async def interrupt_session(
    session_id: str,
    redis: RedisDep,
    access: WorkspaceEditor,
) -> dict[str, str]:
    meta = await _load_session(redis, session_id)
    _guard(meta, access.user.id)
    await _push_op(redis, {"op": "interrupt", "session_id": session_id})
    return {"status": "accepted"}


@router.post("/sessions/{session_id}/restart", status_code=status.HTTP_202_ACCEPTED)
async def restart_session(
    session_id: str,
    redis: RedisDep,
    access: WorkspaceEditor,
) -> dict[str, str]:
    meta = await _load_session(redis, session_id)
    _guard(meta, access.user.id)
    await _push_op(redis, {"op": "restart", "session_id": session_id})
    return {"status": "accepted"}


@router.delete("/sessions/{session_id}", status_code=status.HTTP_202_ACCEPTED)
async def close_session(
    session_id: str,
    redis: RedisDep,
    access: WorkspaceEditor,
) -> dict[str, str]:
    meta = await _load_session(redis, session_id)
    _guard(meta, access.user.id)
    await _push_op(redis, {"op": "shutdown", "session_id": session_id})
    return {"status": "accepted"}
