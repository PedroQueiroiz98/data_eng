"""Regras de negócio de Workflow: CRUD + salvar o grafo (tasks + dependências)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from nbplatform.core.config import get_settings
from nbplatform.core.errors import ConflictError, DomainValidationError, NotFoundError
from nbplatform.domain.dag import validate_dag
from nbplatform.domain.enums import TaskType, WorkflowStatus
from nbplatform.domain.workspace_paths import is_ipynb
from nbplatform.models.job import Job
from nbplatform.models.notebook import Notebook
from nbplatform.models.workflow import Workflow, WorkflowDependency, WorkflowTask
from nbplatform.repositories.workflow_repository import WorkflowRepository
from nbplatform.schemas.workflow import WorkflowEdgeInput, WorkflowTaskInput
from nbplatform.services.workspace_fs_service import WorkspaceFsService
from nbplatform.services.workspace_service import WorkspaceService


class WorkflowService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = WorkflowRepository(session)

    # ── CRUD ────────────────────────────────────────────────────────────────
    async def create(self, *, name: str, description: str | None) -> Workflow:
        workflow = Workflow(name=name, description=description, status=WorkflowStatus.DRAFT)
        await self.repo.add(workflow)
        return workflow

    async def get(self, workflow_id: uuid.UUID) -> Workflow:
        workflow = await self.repo.get_with_graph(workflow_id)
        if workflow is None:
            raise NotFoundError(f"Workflow {workflow_id} não encontrado.")
        return workflow

    async def list_workflows(self, *, limit: int, offset: int) -> list[Workflow]:
        return await self.repo.list_paged(limit=limit, offset=offset)

    async def update_metadata(
        self,
        workflow_id: uuid.UUID,
        *,
        name: str | None,
        description: str | None,
        status: WorkflowStatus | None,
    ) -> Workflow:
        workflow = await self.get(workflow_id)
        if name is not None:
            workflow.name = name
        if description is not None:
            workflow.description = description
        if status is not None:
            workflow.status = status
        await self.session.flush()
        return workflow

    async def delete(self, workflow_id: uuid.UUID) -> None:
        workflow = await self.repo.get(workflow_id)
        if workflow is None:
            raise NotFoundError(f"Workflow {workflow_id} não encontrado.")
        job_count = await self.session.scalar(
            select(func.count()).select_from(Job).where(Job.workflow_id == workflow_id)
        )
        if job_count:
            raise ConflictError(
                f"Workflow tem {job_count} execução(ões) no histórico. "
                "Exclua as execuções antes de excluir o workflow."
            )
        await self.repo.delete(workflow)

    # ── Grafo ──────────────────────────────────────────────────────────────
    async def save_graph(
        self,
        workflow_id: uuid.UUID,
        *,
        tasks: list[WorkflowTaskInput],
        dependencies: list[WorkflowEdgeInput],
    ) -> Workflow:
        workflow = await self.repo.get(workflow_id)
        if workflow is None:
            raise NotFoundError(f"Workflow {workflow_id} não encontrado.")

        keys = [t.key for t in tasks]
        if len(keys) != len(set(keys)):
            raise DomainValidationError("Chaves de tarefa duplicadas no grafo.")
        key_set = set(keys)

        await self._validate_task_types(tasks)

        edge_keys = [(e.from_key, e.to_key) for e in dependencies]
        for src, dst in edge_keys:
            if src not in key_set or dst not in key_set:
                raise DomainValidationError("Dependência referencia tarefa fora do grafo.")
        validate_dag(key_set, edge_keys)

        existing = {t.id: t for t in await self.repo.tasks_for(workflow_id)}
        key_to_id = await self._upsert_tasks(workflow_id, tasks, existing)

        orphan_ids = set(existing) - set(key_to_id.values())
        for oid in orphan_ids:
            await self.session.delete(existing[oid])

        await self.repo.clear_dependencies(workflow_id)
        await self.session.flush()

        seen: set[tuple[uuid.UUID, uuid.UUID]] = set()
        for src, dst in edge_keys:
            pair = (key_to_id[src], key_to_id[dst])
            if pair in seen:
                continue
            seen.add(pair)
            self.session.add(
                WorkflowDependency(
                    workflow_id=workflow_id, from_task_id=pair[0], to_task_id=pair[1]
                )
            )

        try:
            await self.session.flush()
        except IntegrityError as exc:  # p.ex. task referenciada por um Job (FK RESTRICT)
            raise ConflictError(
                "Não foi possível salvar o grafo: alguma tarefa removida ainda é "
                "referenciada por um Job."
            ) from exc

        return await self.get(workflow_id)

    # ── helpers ────────────────────────────────────────────────────────────
    async def _validate_task_types(self, tasks: list[WorkflowTaskInput]) -> None:
        legacy_notebook_ids: set[uuid.UUID] = set()
        for task in tasks:
            if task.type is not TaskType.NOTEBOOK:
                raise DomainValidationError(
                    f"Tipo de tarefa não suportado nesta fase: {task.type}."
                )
            if task.workspace_id is not None and task.notebook_path:
                await self._validate_workspace_notebook(
                    task.name, task.workspace_id, task.notebook_path
                )
            elif task.notebook_id is not None:
                legacy_notebook_ids.add(task.notebook_id)  # workflow antigo
            else:
                raise DomainValidationError(
                    f"Tarefa '{task.name}' precisa de um notebook do Workspace "
                    "(workspace_id + notebook_path)."
                )

        if legacy_notebook_ids:
            found = set(
                await self.session.scalars(
                    select(Notebook.id).where(Notebook.id.in_(legacy_notebook_ids))
                )
            )
            missing = legacy_notebook_ids - found
            if missing:
                raise DomainValidationError(
                    f"Notebook(s) inexistente(s): {sorted(str(m) for m in missing)}."
                )

    async def _validate_workspace_notebook(
        self, task_name: str, workspace_id: uuid.UUID, notebook_path: str
    ) -> None:
        if not is_ipynb(notebook_path):
            raise DomainValidationError(
                f"Tarefa '{task_name}': o caminho deve apontar para um .ipynb."
            )
        try:
            await WorkspaceService(self.session).get_active(workspace_id)
        except NotFoundError as exc:
            raise DomainValidationError(f"Tarefa '{task_name}': Workspace não encontrado.") from exc
        settings = get_settings()
        fs = WorkspaceFsService(
            WorkspaceService(self.session).root_for(workspace_id),
            max_upload_bytes=settings.workspace_max_upload_bytes,
            max_nodes=settings.workspace_tree_max_nodes,
            max_depth=settings.workspace_tree_max_depth,
        )
        try:
            await fs.read_file(notebook_path)
        except NotFoundError as exc:
            raise DomainValidationError(
                f"Tarefa '{task_name}': notebook não encontrado no Workspace ({notebook_path})."
            ) from exc

    async def _upsert_tasks(
        self,
        workflow_id: uuid.UUID,
        tasks: list[WorkflowTaskInput],
        existing: dict[uuid.UUID, WorkflowTask],
    ) -> dict[str, uuid.UUID]:
        key_to_id: dict[str, uuid.UUID] = {}
        for task in tasks:
            existing_id = _maybe_uuid(task.key)
            row = existing.get(existing_id) if existing_id else None
            if row is None:
                row = WorkflowTask(workflow_id=workflow_id)
                self.session.add(row)
            _apply(row, task)
            await self.session.flush()
            key_to_id[task.key] = row.id
        return key_to_id


def _maybe_uuid(value: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(value)
    except ValueError:
        return None


def _apply(row: WorkflowTask, task: WorkflowTaskInput) -> None:
    row.name = task.name
    row.type = task.type
    row.notebook_id = task.notebook_id
    row.workspace_id = task.workspace_id
    row.notebook_path = task.notebook_path
    row.parameters = task.parameters
    row.timeout_s = task.timeout_s
    row.max_retries = task.max_retries
    row.retry_policy = task.retry_policy
    row.ui_position = _position_dict(task.ui_position)


def _position_dict(pos: dict[str, float] | None) -> dict[str, Any] | None:
    if pos is None:
        return None
    return {"x": float(pos.get("x", 0)), "y": float(pos.get("y", 0))}
