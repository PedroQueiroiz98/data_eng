"""WebSocket de acompanhamento: snapshot + eventos em tempo real (execução, job, kernel)."""

from __future__ import annotations

import asyncio
import contextlib
import json
import uuid
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from nbplatform.core.config import get_settings
from nbplatform.core.errors import NotFoundError
from nbplatform.db.session import session_scope
from nbplatform.queue.redis_client import get_redis
from nbplatform.schemas.execution import ExecutionDetail, ExecutionLogRead
from nbplatform.schemas.job import JobLogRead
from nbplatform.services.execution_service import ExecutionService
from nbplatform.services.job_service import JobService
from nbplatform.ws.events import (
    subscribe_execution_events,
    subscribe_job_events,
    subscribe_kernel_events,
    subscribe_workspace_events,
)

router = APIRouter()

_TERMINAL_EXEC = {"SUCCESS", "FAILED", "CANCELLED", "TIMEOUT"}
_TERMINAL_JOB = {"SUCCESS", "FAILED", "CANCELLED"}


def _claims(websocket: WebSocket) -> dict[str, Any] | None:
    """Decodifica o JWT de ?token= (Bearer não é prático no handshake)."""
    import jwt

    from nbplatform.core.security import decode_access_token

    token = websocket.query_params.get("token")
    if not token:
        return None
    try:
        return decode_access_token(token)
    except jwt.PyJWTError:
        return None


def _authenticated(websocket: WebSocket) -> bool:
    return _claims(websocket) is not None


@router.websocket("/ws/executions/{execution_id}")
async def execution_ws(websocket: WebSocket, execution_id: str) -> None:
    await websocket.accept()
    if not _authenticated(websocket):
        await websocket.close(code=1008)
        return
    try:
        exec_uuid = uuid.UUID(execution_id)
    except ValueError:
        await websocket.close(code=1008)
        return

    after_seq = int(websocket.query_params.get("after_seq", "0") or 0)
    try:
        async with session_scope() as session:
            service = ExecutionService(session)
            execution = await service.get(exec_uuid)
            logs = await service.logs_since(exec_uuid, after_seq=after_seq)
            detail = ExecutionDetail.model_validate(execution)
            detail.has_output = execution.output_notebook is not None
            snapshot = {
                "type": "snapshot",
                "execution": detail.model_dump(mode="json"),
                "logs": [
                    ExecutionLogRead.model_validate(log).model_dump(mode="json") for log in logs
                ],
            }
    except NotFoundError:
        await websocket.close(code=1008)
        return

    await _stream(
        websocket,
        snapshot,
        subscribe_execution_events(get_redis(), execution_id),
        terminal=_TERMINAL_EXEC,
    )


@router.websocket("/ws/jobs/{job_id}")
async def job_ws(websocket: WebSocket, job_id: str) -> None:
    await websocket.accept()
    if not _authenticated(websocket):
        await websocket.close(code=1008)
        return
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        await websocket.close(code=1008)
        return

    after_seq = int(websocket.query_params.get("after_seq", "0") or 0)
    try:
        async with session_scope() as session:
            service = JobService(session)
            detail = await service.detail(job_uuid)
            logs = await service.logs_since(job_uuid, after_seq=after_seq)
            job_json = detail.model_dump(mode="json")
            tasks = job_json.pop("tasks", [])
            snapshot = {
                "type": "snapshot",
                "job": job_json,
                "tasks": tasks,
                "logs": [JobLogRead.model_validate(log).model_dump(mode="json") for log in logs],
            }
    except NotFoundError:
        await websocket.close(code=1008)
        return

    await _stream(
        websocket,
        snapshot,
        subscribe_job_events(get_redis(), job_id),
        terminal=_TERMINAL_JOB,
    )


@router.websocket("/ws/kernels/{session_id}")
async def kernel_ws(websocket: WebSocket, session_id: str) -> None:
    await websocket.accept()
    claims = _claims(websocket)
    if claims is None:
        await websocket.close(code=1008)
        return

    settings = get_settings()
    redis = get_redis()
    meta = await redis.hgetall(settings.kernel_sess_key(session_id))
    user_id = str(claims.get("sub", ""))
    # Single-workspace: basta ser o dono da sessão de kernel (ou admin global).
    if not meta or (meta.get("user_id") != user_id and claims.get("role") != "admin"):
        await websocket.close(code=1008)
        return

    after_seq = int(websocket.query_params.get("after_seq", "0") or 0)
    raw_events = await redis.lrange(settings.kernel_log_key(session_id), 0, -1)
    events: list[dict[str, Any]] = []
    for raw in raw_events:
        try:
            evt = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if int(evt.get("seq", 0)) > after_seq:
            events.append(evt)
    snapshot = {
        "type": "snapshot",
        "session": {
            "session_id": session_id,
            "status": meta.get("status", "starting"),
            "execution_count": int(meta.get("execution_count") or 0),
            "notebook_path": meta.get("notebook_path", ""),
        },
        "events": events,
    }

    await websocket.send_json(snapshot)
    async with subscribe_kernel_events(redis, session_id) as stream:
        client_gone = asyncio.create_task(_wait_client_close(websocket))
        try:
            async for event in stream:
                if client_gone.done():
                    break
                await websocket.send_json(event)
        except WebSocketDisconnect:
            pass
        finally:
            client_gone.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await client_gone
    with contextlib.suppress(RuntimeError):
        await websocket.close()


@router.websocket("/ws/workspace")
async def workspace_ws(websocket: WebSocket) -> None:
    """Eventos de filesystem do Workspace único (File Explorer em tempo real).

    Snapshot = árvore atual + `seq`; depois relay dos `fs.batch` do watcher.
    `?after_seq=` replaia o buffer Redis para não perder eventos numa reconexão.
    """
    await websocket.accept()
    if not _authenticated(websocket):
        await websocket.close(code=1008)
        return

    from nbplatform.core.config import get_settings as _get_settings
    from nbplatform.schemas.workspace import FileNode as _FileNode
    from nbplatform.services.workspace_fs_service import WorkspaceFsService

    settings = _get_settings()
    redis = get_redis()
    after_seq = int(websocket.query_params.get("after_seq", "0") or 0)

    fs = WorkspaceFsService(
        Path(settings.workspace_dir),
        max_upload_bytes=settings.workspace_max_upload_bytes,
        max_nodes=settings.workspace_tree_max_nodes,
        max_depth=settings.workspace_tree_max_depth,
    )
    try:
        tree = await fs.list_tree(rel_path="")
        tree_json = _FileNode.model_validate(tree, from_attributes=True).model_dump(mode="json")
    except Exception:  # noqa: BLE001
        tree_json = {"name": "", "path": "", "type": "dir", "children": []}

    seq_raw = await redis.get(settings.redis_workspace_seq_key)
    current_seq = int(seq_raw or 0)

    buffered: list[dict[str, Any]] = []
    if after_seq and after_seq < current_seq:
        for raw in await redis.lrange(settings.redis_workspace_log_key, 0, -1):
            try:
                evt = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if int(evt.get("seq", 0)) > after_seq:
                buffered.append(evt)

    await websocket.send_json(
        {"type": "snapshot", "tree": tree_json, "seq": current_seq}
    )
    for evt in buffered:
        await websocket.send_json(evt)

    async with subscribe_workspace_events(redis) as stream:
        client_gone = asyncio.create_task(_wait_client_close(websocket))
        try:
            async for event in stream:
                if client_gone.done():
                    break
                await websocket.send_json(event)
        except WebSocketDisconnect:
            pass
        finally:
            client_gone.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await client_gone
    with contextlib.suppress(RuntimeError):
        await websocket.close()


async def _stream(  # type: ignore[no-untyped-def]
    websocket: WebSocket,
    snapshot: Mapping[str, object],
    subscription,
    terminal: set[str],
) -> None:
    await websocket.send_json(snapshot)
    async with subscription as events:
        client_gone = asyncio.create_task(_wait_client_close(websocket))
        try:
            async for event in events:
                if client_gone.done():
                    break
                await websocket.send_json(event)
                if event.get("type") == "status_changed" and event.get("status") in terminal:
                    break
        except WebSocketDisconnect:
            pass
        finally:
            client_gone.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await client_gone
    with contextlib.suppress(RuntimeError):
        await websocket.close()


async def _wait_client_close(websocket: WebSocket) -> None:
    with contextlib.suppress(WebSocketDisconnect):
        while True:
            await websocket.receive_text()
