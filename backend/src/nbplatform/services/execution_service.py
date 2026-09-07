"""Regras de negócio de Execution: criação, consulta e transições de estado."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from nbplatform.core.errors import ConflictError, NotFoundError
from nbplatform.domain.enums import ExecutionStatus, LogLevel
from nbplatform.domain.state_machine import assert_transition
from nbplatform.models.execution import Execution, ExecutionLog
from nbplatform.repositories.execution_repository import ExecutionRepository
from nbplatform.repositories.notebook_repository import NotebookRepository


def _now() -> datetime:
    return datetime.now(UTC)


class ExecutionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = ExecutionRepository(session)
        self.notebooks = NotebookRepository(session)

    # ── API ──────────────────────────────────────────────────────────────────
    async def create_for_notebook(
        self,
        notebook_id: uuid.UUID,
        *,
        parameters: dict[str, Any],
        version_number: int | None,
        idempotency_key: str | None,
    ) -> tuple[Execution, bool]:
        """Retorna (execution, created). `created=False` se caiu numa idempotency_key existente."""
        if idempotency_key:
            existing = await self.repo.get_by_idempotency_key(idempotency_key)
            if existing is not None:
                return existing, False

        notebook = await self.notebooks.get(notebook_id)
        if notebook is None:
            raise NotFoundError(f"Notebook {notebook_id} não encontrado.")

        target_version = version_number or notebook.current_version
        version = await self.notebooks.get_version(notebook_id, target_version)
        if version is None:
            raise NotFoundError(
                f"Versão {target_version} do notebook {notebook_id} não encontrada."
            )

        execution = Execution(
            notebook_version_id=version.id,
            status=ExecutionStatus.QUEUED,
            parameters=parameters,
            attempt=1,
            idempotency_key=idempotency_key,
        )
        await self.repo.add(execution)
        return execution, True

    async def create_raw(
        self,
        notebook_version_id: uuid.UUID,
        *,
        parameters: dict[str, Any],
        retry_policy: dict[str, Any] | None = None,
        timeout_s: int | None = None,
    ) -> Execution:
        """Cria uma execução para uma versão específica (usado pela orquestração de Jobs)."""
        execution = Execution(
            notebook_version_id=notebook_version_id,
            status=ExecutionStatus.QUEUED,
            parameters=parameters,
            attempt=1,
            retry_policy=retry_policy or None,
            timeout_s=timeout_s,
        )
        await self.repo.add(execution)
        return execution

    async def get(self, execution_id: uuid.UUID) -> Execution:
        execution = await self.repo.get(execution_id)
        if execution is None:
            raise NotFoundError(f"Execução {execution_id} não encontrada.")
        return execution

    async def list_executions(
        self,
        *,
        limit: int,
        offset: int,
        status: ExecutionStatus | None,
    ) -> list[Execution]:
        return await self.repo.list_paged(limit=limit, offset=offset, status=status)

    async def logs_since(
        self, execution_id: uuid.UUID, *, after_seq: int
    ) -> list[ExecutionLog]:
        return await self.repo.logs_since(execution_id, after_seq=after_seq)

    # ── Worker: transições ───────────────────────────────────────────────────
    async def mark_running(
        self, execution_id: uuid.UUID, *, worker_id: str, attempt: int
    ) -> Execution:
        execution = await self._locked(execution_id)
        assert_transition(execution.status, ExecutionStatus.RUNNING)
        execution.status = ExecutionStatus.RUNNING
        execution.attempt = attempt
        execution.worker_id = worker_id
        execution.started_at = _now()
        execution.last_heartbeat = _now()
        await self.session.flush()
        return execution

    async def heartbeat(self, execution_id: uuid.UUID) -> None:
        execution = await self.repo.get(execution_id)
        if execution and execution.status == ExecutionStatus.RUNNING:
            execution.last_heartbeat = _now()
            await self.session.flush()

    async def append_log(
        self,
        execution_id: uuid.UUID,
        *,
        seq: int,
        level: LogLevel,
        message: str,
        attempt: int,
    ) -> ExecutionLog:
        log = ExecutionLog(
            execution_id=execution_id,
            ts=_now(),
            level=level,
            message=message,
            attempt=attempt,
            seq=seq,
        )
        await self.repo.add_log(log)
        return log

    async def finish(
        self,
        execution_id: uuid.UUID,
        *,
        status: ExecutionStatus,
        error_code: str | None = None,
        error_message: str | None = None,
        output_notebook: dict[str, Any] | None = None,
        output_notebook_path: str | None = None,
    ) -> Execution:
        execution = await self._locked(execution_id)
        assert_transition(execution.status, status)
        execution.status = status
        execution.finished_at = _now()
        if execution.started_at is not None:
            delta = execution.finished_at - execution.started_at
            execution.duration_ms = int(delta.total_seconds() * 1000)
        execution.error_code = error_code
        execution.error_message = error_message
        if output_notebook is not None:
            execution.output_notebook = output_notebook
        if output_notebook_path is not None:
            execution.output_notebook_path = output_notebook_path
        await self.session.flush()
        return execution

    async def cancel(self, execution_id: uuid.UUID) -> tuple[Execution, bool]:
        """Idempotente. Retorna (execution, changed). QUEUED→CANCELLED direto;
        RUNNING marca a intenção (o worker termina o processo) e transiciona aqui
        apenas se ainda não estiver rodando de fato."""
        execution = await self._locked(execution_id)
        if execution.status in (ExecutionStatus.QUEUED,):
            execution.status = ExecutionStatus.CANCELLED
            execution.finished_at = _now()
            await self.session.flush()
            return execution, True
        return execution, False

    async def mark_cancelled(self, execution_id: uuid.UUID) -> Execution:
        execution = await self._locked(execution_id)
        assert_transition(execution.status, ExecutionStatus.CANCELLED)
        execution.status = ExecutionStatus.CANCELLED
        execution.finished_at = _now()
        if execution.started_at is not None:
            execution.duration_ms = int(
                (execution.finished_at - execution.started_at).total_seconds() * 1000
            )
        await self.session.flush()
        return execution

    async def requeue_for_retry(self, execution_id: uuid.UUID) -> Execution:
        """FAILED/TIMEOUT → QUEUED, incrementa attempt, limpa erro/tempos."""
        execution = await self._locked(execution_id)
        assert_transition(execution.status, ExecutionStatus.QUEUED)
        execution.status = ExecutionStatus.QUEUED
        execution.attempt += 1
        execution.started_at = None
        execution.finished_at = None
        execution.duration_ms = None
        execution.error_code = None
        execution.error_message = None
        execution.worker_id = None
        execution.last_heartbeat = None
        await self.session.flush()
        return execution

    async def force_fail(
        self, execution_id: uuid.UUID, *, error_code: str, error_message: str
    ) -> Execution | None:
        """Usado pela recovery: RUNNING abandonado → FAILED. None se já não é RUNNING."""
        execution = await self._locked(execution_id)
        if execution.status is not ExecutionStatus.RUNNING:
            return None
        execution.status = ExecutionStatus.FAILED
        execution.finished_at = _now()
        execution.error_code = error_code
        execution.error_message = error_message
        await self.session.flush()
        return execution

    async def list_stale_running(self, *, older_than: datetime) -> list[Execution]:
        return await self.repo.list_stale_running(older_than=older_than)

    async def _locked(self, execution_id: uuid.UUID) -> Execution:
        execution = await self.repo.get_for_update(execution_id)
        if execution is None:
            raise ConflictError(f"Execução {execution_id} não encontrada para transição.")
        return execution
