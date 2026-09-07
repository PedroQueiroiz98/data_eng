"""Orquestra uma execução: transições, materialização, Papermill, logs, output."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from redis.asyncio import Redis

from nbplatform.core.config import get_settings
from nbplatform.core.errors import ConflictError
from nbplatform.db.session import session_scope
from nbplatform.domain.enums import ExecutionStatus, LogLevel
from nbplatform.queue.execution_queue import ExecutionQueue
from nbplatform.services.execution_service import ExecutionService
from nbplatform.worker.papermill_executor import run_papermill
from nbplatform.ws.events import make_event, publish_execution_event

logger = logging.getLogger(__name__)


class ExecutionManager:
    def __init__(self, redis: Redis, *, worker_id: str) -> None:
        self.redis = redis
        self.worker_id = worker_id
        self.settings = get_settings()
        self.queue = ExecutionQueue(redis)

    async def run(self, execution_id: str, *, attempt: int) -> ExecutionStatus:
        exec_uuid = uuid.UUID(execution_id)
        workdir = Path(self.settings.executions_dir) / execution_id
        workdir.mkdir(parents=True, exist_ok=True)

        try:
            content = await self._start(exec_uuid, attempt)
        except ConflictError:
            logger.info("execução não está QUEUED; ignorando", extra={"execution_id": execution_id})
            return ExecutionStatus.CANCELLED

        input_path = workdir / "input.ipynb"
        output_path = workdir / "output.ipynb"
        params_path = workdir / "params.json"
        input_path.write_text(json.dumps(_ensure_language(content)), encoding="utf-8")
        params_path.write_text(json.dumps(await self._parameters(exec_uuid)), encoding="utf-8")

        heartbeat_task = asyncio.create_task(self._heartbeat_loop(exec_uuid))
        try:
            result = await run_papermill(
                input_path=str(input_path),
                output_path=str(output_path),
                params_path=str(params_path),
                timeout_s=float(self.settings.execution_timeout_s),
                on_line=lambda line: self._emit_log(exec_uuid, attempt, line),
            )
        finally:
            heartbeat_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await heartbeat_task

        output_nb = _read_notebook(output_path)

        if result.succeeded:
            status = ExecutionStatus.SUCCESS
            error_code = error_message = None
        elif result.timed_out:
            status = ExecutionStatus.TIMEOUT
            error_code, error_message = "TIMEOUT", result.error_summary
        else:
            status = ExecutionStatus.FAILED
            error_code = "NOTEBOOK_ERROR" if result.is_notebook_error else "WORKER_ERROR"
            error_message = result.error_summary or f"exit code {result.exit_code}"

        await self._finish(
            exec_uuid,
            status=status,
            error_code=error_code,
            error_message=error_message,
            output_notebook=output_nb,
            output_notebook_path=str(output_path) if output_path.exists() else None,
        )
        return status

    # ── passos ───────────────────────────────────────────────────────────────
    async def _start(self, exec_uuid: uuid.UUID, attempt: int) -> dict[str, Any]:
        async with session_scope() as session:
            service = ExecutionService(session)
            execution = await service.mark_running(
                exec_uuid, worker_id=self.worker_id, attempt=attempt
            )
            version = await service.notebooks.get_version_by_id(execution.notebook_version_id)
            assert version is not None  # FK garante existência
            content: dict[str, Any] = version.content
        await self._publish(exec_uuid, make_event("status_changed", status=ExecutionStatus.RUNNING))
        return content

    async def _parameters(self, exec_uuid: uuid.UUID) -> dict[str, Any]:
        async with session_scope() as session:
            execution = await ExecutionService(session).get(exec_uuid)
            return dict(execution.parameters or {})

    async def _emit_log(self, exec_uuid: uuid.UUID, attempt: int, line: str) -> None:
        seq = await self.queue.next_seq(str(exec_uuid))
        level = LogLevel.ERROR if line.startswith("PAPERMILL_ERROR::") else LogLevel.INFO
        async with session_scope() as session:
            await ExecutionService(session).append_log(
                exec_uuid, seq=seq, level=level, message=line, attempt=attempt
            )
        await self._publish(
            exec_uuid,
            make_event(
                "log",
                seq=seq,
                level=level,
                message=line,
                attempt=attempt,
                ts=datetime.now(UTC).isoformat(),
            ),
        )

    async def _finish(
        self,
        exec_uuid: uuid.UUID,
        *,
        status: ExecutionStatus,
        error_code: str | None,
        error_message: str | None,
        output_notebook: dict[str, Any] | None,
        output_notebook_path: str | None,
    ) -> None:
        async with session_scope() as session:
            await ExecutionService(session).finish(
                exec_uuid,
                status=status,
                error_code=error_code,
                error_message=error_message,
                output_notebook=output_notebook,
                output_notebook_path=output_notebook_path,
            )
        if output_notebook is not None:
            await self._publish(exec_uuid, make_event("output", available=True))
        await self._publish(
            exec_uuid,
            make_event("status_changed", status=status, error_message=error_message),
        )

    async def _heartbeat_loop(self, exec_uuid: uuid.UUID) -> None:
        interval = self.settings.worker_heartbeat_interval_s
        while True:
            await asyncio.sleep(interval)
            with contextlib.suppress(Exception):
                async with session_scope() as session:
                    await ExecutionService(session).heartbeat(exec_uuid)
            await self._publish(exec_uuid, make_event("progress", heartbeat=True))

    async def _publish(self, exec_uuid: uuid.UUID, event: dict[str, Any]) -> None:
        with contextlib.suppress(Exception):
            await publish_execution_event(self.redis, str(exec_uuid), event)


def _ensure_language(content: dict[str, Any]) -> dict[str, Any]:
    """Papermill exige language_info/kernelspec. Fase 3 suporta apenas Python."""
    meta = content.setdefault("metadata", {})
    meta.setdefault("language_info", {"name": "python"})
    meta.setdefault("kernelspec", {"name": "python3", "display_name": "Python 3"})
    return content


def _read_notebook(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        return data
    except (OSError, json.JSONDecodeError):
        return None


def cleanup_workdir(execution_id: str) -> None:
    workdir = Path(get_settings().executions_dir) / execution_id
    with contextlib.suppress(OSError):
        shutil.rmtree(workdir)
