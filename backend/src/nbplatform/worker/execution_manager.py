"""Orquestra uma execução: transições, materialização, Papermill, logs, output, retry."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from redis.asyncio import Redis

from nbplatform.core.config import get_settings
from nbplatform.core.errors import ConflictError
from nbplatform.core.masking import mask_secrets
from nbplatform.db.session import session_scope
from nbplatform.domain.enums import ExecutionSource, ExecutionStatus, LogLevel
from nbplatform.domain.notebook_format import read_dependencies
from nbplatform.domain.workspace_paths import resolve_within
from nbplatform.queue.execution_queue import ExecutionQueue
from nbplatform.services.execution_service import ExecutionService
from nbplatform.services.retry_coordinator import RetryCoordinator
from nbplatform.services.secret_service import SecretService
from nbplatform.services.variable_service import VariableService
from nbplatform.worker.pip_installer import install_packages
from nbplatform.worker.sandbox import run_sandboxed
from nbplatform.ws.events import make_event, publish_execution_event

logger = logging.getLogger(__name__)

CANCEL_POLL_INTERVAL_S = 2.0


class ExecutionManager:
    def __init__(self, redis: Redis, *, worker_id: str) -> None:
        self.redis = redis
        self.worker_id = worker_id
        self.settings = get_settings()
        self.queue = ExecutionQueue(redis)
        self._secret_values: list[str] = []

    async def run(self, execution_id: str, *, attempt: int) -> ExecutionStatus:
        exec_uuid = uuid.UUID(execution_id)
        workdir = Path(self.settings.executions_dir) / execution_id
        workdir.mkdir(parents=True, exist_ok=True)

        try:
            content, timeout_s, workspace_root = await self._start(exec_uuid, attempt)
        except ConflictError:
            logger.info(
                "execução não está QUEUED; ignorando", extra={"execution_id": execution_id}
            )
            await self.queue.clear_cancel(execution_id)
            return ExecutionStatus.CANCELLED

        input_path = workdir / "input.ipynb"
        output_path = workdir / "output.ipynb"
        params_path = workdir / "params.json"
        pydeps_dir = workdir / ".pydeps"
        pydeps_dir.mkdir(parents=True, exist_ok=True)
        input_path.write_text(json.dumps(_ensure_language(content)), encoding="utf-8")
        params_path.write_text(
            json.dumps(await self._parameters(exec_uuid)), encoding="utf-8"
        )

        env = await self._build_env(pydeps_dir, workspace_root=workspace_root)

        if not await self._install_dependencies(exec_uuid, attempt, content, pydeps_dir):
            msg = "falha ao instalar dependências declaradas (pip)"
            await self._finish(
                exec_uuid, ExecutionStatus.FAILED, "DEPENDENCY_ERROR", msg, None, None
            )
            return await self._handle_failure(
                exec_uuid, ExecutionStatus.FAILED, "DEPENDENCY_ERROR", msg
            )

        cancel_event = asyncio.Event()
        heartbeat_task = asyncio.create_task(self._heartbeat_loop(exec_uuid))
        cancel_watch = asyncio.create_task(self._cancel_watch(execution_id, cancel_event))
        try:
            result = await run_sandboxed(
                workdir=str(workdir),
                input_path=str(input_path),
                output_path=str(output_path),
                params_path=str(params_path),
                env=env,
                timeout_s=float(timeout_s or self.settings.execution_timeout_s),
                on_line=lambda line: self._emit_log(exec_uuid, attempt, line),
                cancel_event=cancel_event,
            )
        finally:
            for task in (heartbeat_task, cancel_watch):
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

        output_nb = self._mask_notebook(_read_notebook(output_path))
        output_path_str = str(output_path) if output_path.exists() else None

        # ── cancelamento ─────────────────────────────────────────────────────
        if result.cancelled:
            await self._save_output(exec_uuid, output_nb, output_path_str)
            async with session_scope() as session:
                await ExecutionService(session).mark_cancelled(exec_uuid)
            await self.queue.clear_cancel(execution_id)
            await self._publish(
                exec_uuid, make_event("status_changed", status=ExecutionStatus.CANCELLED)
            )
            return ExecutionStatus.CANCELLED

        # ── sucesso ──────────────────────────────────────────────────────────
        if result.succeeded:
            await self._finish(
                exec_uuid,
                ExecutionStatus.SUCCESS,
                None,
                None,
                output_nb,
                output_path_str,
            )
            await self._publish(
                exec_uuid, make_event("status_changed", status=ExecutionStatus.SUCCESS)
            )
            return ExecutionStatus.SUCCESS

        # ── falha: FAILED ou TIMEOUT ────────────────────────────────────────
        if result.timed_out:
            failed_status = ExecutionStatus.TIMEOUT
            error_code: str = "TIMEOUT"
        else:
            failed_status = ExecutionStatus.FAILED
            error_code = "NOTEBOOK_ERROR" if result.is_notebook_error else "WORKER_ERROR"
        error_message = result.error_summary or f"exit code {result.exit_code}"

        await self._finish(
            exec_uuid, failed_status, error_code, error_message, output_nb, output_path_str
        )
        return await self._handle_failure(
            exec_uuid, failed_status, error_code, error_message
        )

    async def _handle_failure(
        self,
        exec_uuid: uuid.UUID,
        failed_status: ExecutionStatus,
        error_code: str,
        error_message: str,
    ) -> ExecutionStatus:
        async with session_scope() as session:
            decision = await RetryCoordinator(session).decide_and_apply(
                exec_uuid,
                failed_status=failed_status,
                error_code=error_code,
                error_message=error_message,
            )
        # efeitos no Redis só depois do commit
        if decision.action == "retry":
            await self.queue.enqueue_delayed(
                str(exec_uuid), attempt=decision.next_attempt, ready_at=decision.ready_at
            )
            await self._publish(
                exec_uuid,
                make_event(
                    "status_changed",
                    status=ExecutionStatus.QUEUED,
                    retry_in_s=round(decision.delay_s, 1),
                    attempt=decision.next_attempt,
                ),
            )
            logger.info(
                "retry agendado",
                extra={
                    "execution_id": str(exec_uuid),
                    "attempt": decision.next_attempt,
                    "delay_s": decision.delay_s,
                },
            )
            return ExecutionStatus.QUEUED

        await self.queue.dead_letter(
            str(exec_uuid), attempt=decision.attempt, reason=f"{error_code}: {decision.reason}"
        )
        await self._publish(
            exec_uuid,
            make_event(
                "status_changed", status=failed_status, error_message=error_message
            ),
        )
        return failed_status

    # ── passos ───────────────────────────────────────────────────────────────
    async def _start(
        self, exec_uuid: uuid.UUID, attempt: int
    ) -> tuple[dict[str, Any], int | None, str | None]:
        async with session_scope() as session:
            service = ExecutionService(session)
            execution = await service.mark_running(
                exec_uuid, worker_id=self.worker_id, attempt=attempt
            )
            timeout_s = execution.timeout_s
            source = execution.source
            workspace_id = execution.workspace_id
            notebook_path = execution.notebook_path
            notebook_version_id = execution.notebook_version_id
            if source == ExecutionSource.WORKSPACE:
                assert workspace_id is not None and notebook_path is not None, (
                    "execução WORKSPACE sem workspace_id/notebook_path"
                )
                root = Path(self.settings.workspaces_dir) / str(workspace_id)
                content: dict[str, Any] = _read_workspace_notebook(root, notebook_path)
                # subprocess sandbox: o filho compartilha o FS do worker, então o
                # workspace_sdk enxerga esta raiz. No sandbox docker o volume ainda
                # não é montado no container aninhado (pendente Fase 12).
                workspace_root: str | None = str(root)
            else:
                assert notebook_version_id is not None, (
                    "execução DB sem notebook_version_id"
                )
                version = await service.notebooks.get_version_by_id(notebook_version_id)
                assert version is not None  # FK garante existência
                content = version.content
                workspace_root = None
        await self._publish(
            exec_uuid, make_event("status_changed", status=ExecutionStatus.RUNNING)
        )
        return content, timeout_s, workspace_root

    async def _parameters(self, exec_uuid: uuid.UUID) -> dict[str, Any]:
        async with session_scope() as session:
            execution = await ExecutionService(session).get(exec_uuid)
            return dict(execution.parameters or {})

    def _mask_notebook(self, nb: dict[str, Any] | None) -> dict[str, Any] | None:
        """Mascara valores de secrets no output.ipynb (nunca gravar segredo em notebook)."""
        if nb is None or not self._secret_values:
            return nb
        masked: dict[str, Any] = json.loads(
            mask_secrets(json.dumps(nb), self._secret_values)
        )
        return masked

    async def _build_env(
        self, pydeps_dir: Path, *, workspace_root: str | None = None
    ) -> dict[str, str]:
        """Variáveis (visíveis) + secrets (cifrados) + alvo pip → env vars da execução."""
        async with session_scope() as session:
            variables = await VariableService(session).resolve()
            secrets = await SecretService(session).resolve_all()
        self._secret_values = [v for v in secrets.values() if v]
        merged: dict[str, str] = {}
        merged.update({k: str(v) for k, v in variables.items()})
        merged.update({k: str(v) for k, v in secrets.items()})
        merged.update(self._pip_env(pydeps_dir))
        if workspace_root:
            # liga o pacote `workspace_sdk` dentro do notebook (workspace.read_csv(...))
            merged["WORKSPACE_ROOT"] = workspace_root
        return merged

    def _pip_env(self, pydeps_dir: Path) -> dict[str, str]:
        """Isola instalações pip da execução num diretório próprio.

        `PIP_TARGET` faz `%pip install` (e `!pip`) escreverem ali; `PYTHONPATH`
        deixa os pacotes importáveis. No sandbox Docker o workdir é montado em
        `/work`, então os caminhos são reescritos para dentro do container.
        """
        if not self.settings.execution_pip_install:
            return {}
        if self.settings.execution_sandbox == "docker":
            deps_path = "/work/.pydeps"
        else:
            deps_path = str(pydeps_dir)
        prev = os.environ.get("PYTHONPATH", "")
        pythonpath = os.pathsep.join([deps_path, prev]) if prev else deps_path
        env = {
            "PIP_TARGET": deps_path,
            "PIP_NO_INPUT": "1",
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
            "PYTHONPATH": pythonpath,
        }
        if self.settings.execution_pip_index_url:
            env["PIP_INDEX_URL"] = self.settings.execution_pip_index_url
        return env

    async def _install_dependencies(
        self,
        exec_uuid: uuid.UUID,
        attempt: int,
        content: dict[str, Any],
        pydeps_dir: Path,
    ) -> bool:
        """Instala `metadata.nbplatform.dependencies` antes de rodar o notebook."""
        if not self.settings.execution_pip_install:
            return True
        packages = read_dependencies(content)[: self.settings.execution_pip_max_packages]
        if not packages:
            return True
        await self._emit_log(
            exec_uuid,
            attempt,
            f"instalando {len(packages)} dependência(s): {', '.join(packages)}",
        )
        return await install_packages(
            target_dir=str(pydeps_dir),
            packages=packages,
            on_line=lambda line: self._emit_log(exec_uuid, attempt, line),
            timeout_s=float(self.settings.execution_pip_timeout_s),
            index_url=self.settings.execution_pip_index_url or None,
        )

    async def _emit_log(self, exec_uuid: uuid.UUID, attempt: int, line: str) -> None:
        if self._secret_values:
            line = mask_secrets(line, self._secret_values)
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

    async def _save_output(
        self,
        exec_uuid: uuid.UUID,
        output_notebook: dict[str, Any] | None,
        output_notebook_path: str | None,
    ) -> None:
        if output_notebook is None:
            return
        async with session_scope() as session:
            execution = await ExecutionService(session).get(exec_uuid)
            execution.output_notebook = output_notebook
            execution.output_notebook_path = output_notebook_path
        await self._publish(exec_uuid, make_event("output", available=True))

    async def _heartbeat_loop(self, exec_uuid: uuid.UUID) -> None:
        interval = self.settings.worker_heartbeat_interval_s
        while True:
            await asyncio.sleep(interval)
            with contextlib.suppress(Exception):
                async with session_scope() as session:
                    await ExecutionService(session).heartbeat(exec_uuid)
            await self._publish(exec_uuid, make_event("progress", heartbeat=True))

    async def _cancel_watch(self, execution_id: str, cancel_event: asyncio.Event) -> None:
        while not cancel_event.is_set():
            with contextlib.suppress(Exception):
                if await self.queue.is_cancel_requested(execution_id):
                    logger.info("cancelamento solicitado", extra={"execution_id": execution_id})
                    cancel_event.set()
                    return
            await asyncio.sleep(CANCEL_POLL_INTERVAL_S)

    async def _publish(self, exec_uuid: uuid.UUID, event: dict[str, Any]) -> None:
        with contextlib.suppress(Exception):
            await publish_execution_event(self.redis, str(exec_uuid), event)


def _ensure_language(content: dict[str, Any]) -> dict[str, Any]:
    """Papermill exige language_info/kernelspec. Fase 3 suporta apenas Python."""
    meta = content.setdefault("metadata", {})
    meta.setdefault("language_info", {"name": "python"})
    meta.setdefault("kernelspec", {"name": "python3", "display_name": "Python 3"})
    return content


def _read_workspace_notebook(root: Path, rel_path: str) -> dict[str, Any]:
    """Lê e valida um `.ipynb` de dentro de um Workspace (guard de path traversal)."""
    target = resolve_within(root, rel_path)
    if not target.is_file():
        raise FileNotFoundError(f"notebook não encontrado no Workspace: {rel_path}")
    data = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"conteúdo .ipynb inválido: {rel_path}")
    return data


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
