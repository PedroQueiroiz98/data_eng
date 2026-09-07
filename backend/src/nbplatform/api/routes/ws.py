"""WebSocket de acompanhamento: snapshot + eventos em tempo real (execução e job)."""

from __future__ import annotations

import asyncio
import contextlib
import uuid
from collections.abc import Mapping

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from nbplatform.core.errors import NotFoundError
from nbplatform.db.session import session_scope
from nbplatform.queue.redis_client import get_redis
from nbplatform.schemas.execution import ExecutionDetail, ExecutionLogRead
from nbplatform.schemas.job import JobLogRead
from nbplatform.services.execution_service import ExecutionService
from nbplatform.services.job_service import JobService
from nbplatform.ws.events import subscribe_execution_events, subscribe_job_events

router = APIRouter()

_TERMINAL_EXEC = {"SUCCESS", "FAILED", "CANCELLED", "TIMEOUT"}
_TERMINAL_JOB = {"SUCCESS", "FAILED", "CANCELLED"}


def _authenticated(websocket: WebSocket) -> bool:
    """Auth de WebSocket via ?token=<jwt> (Bearer não é prático no handshake)."""
    import jwt

    from nbplatform.core.security import decode_access_token

    token = websocket.query_params.get("token")
    if not token:
        return False
    try:
        decode_access_token(token)
    except jwt.PyJWTError:
        return False
    return True


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
                    ExecutionLogRead.model_validate(log).model_dump(mode="json")
                    for log in logs
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
                "logs": [
                    JobLogRead.model_validate(log).model_dump(mode="json") for log in logs
                ],
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
