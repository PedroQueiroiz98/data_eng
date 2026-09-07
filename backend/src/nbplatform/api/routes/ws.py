"""WebSocket de acompanhamento de execução: snapshot + eventos em tempo real."""

from __future__ import annotations

import asyncio
import contextlib
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from nbplatform.core.errors import NotFoundError
from nbplatform.db.session import session_scope
from nbplatform.queue.redis_client import get_redis
from nbplatform.schemas.execution import ExecutionDetail, ExecutionLogRead
from nbplatform.services.execution_service import ExecutionService
from nbplatform.ws.events import subscribe_execution_events

router = APIRouter()


@router.websocket("/ws/executions/{execution_id}")
async def execution_ws(websocket: WebSocket, execution_id: str) -> None:
    await websocket.accept()
    try:
        exec_uuid = uuid.UUID(execution_id)
    except ValueError:
        await websocket.close(code=1008)
        return

    after_seq = int(websocket.query_params.get("after_seq", "0") or 0)

    # ── snapshot ─────────────────────────────────────────────────────────────
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

    await websocket.send_json(snapshot)

    # ── stream de eventos ────────────────────────────────────────────────────
    redis = get_redis()
    async with subscribe_execution_events(redis, execution_id) as events:
        client_gone = asyncio.create_task(_wait_client_close(websocket))
        try:
            async for event in events:
                if client_gone.done():
                    break
                await websocket.send_json(event)
                if event.get("type") == "status_changed" and _is_terminal(event.get("status")):
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


def _is_terminal(status: object) -> bool:
    return status in {"SUCCESS", "FAILED", "CANCELLED", "TIMEOUT"}
