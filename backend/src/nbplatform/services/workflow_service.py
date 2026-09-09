"""Regras de negócio de Workflow: CRUD + salvar o grafo (tasks + dependências)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from nbplatform.core.config import get_settings
from nbplatform.core.errors import (
    ConflictError,
    DomainValidationError,
    ForbiddenError,
    NotFoundError,
)
from nbplatform.domain.dag import validate_dag
from nbplatform.domain.enums import TaskType, WorkflowStatus
from nbplatform.domain.workspace_paths import is_ipynb
from nbplatform.models.job import Job
from nbplatform.models.notebook import Notebook
from nbplatform.models.workflow import Workflow, WorkflowDependency, WorkflowTask
from nbplatform.repositories.workflow_repository import WorkflowRepository
from nbplatform.schemas.workflow import WorkflowEdgeInput, WorkflowTaskInput
from nbplatform.services.workspace_fs_service import WorkspaceFsService
from nbplatform.services.workspace_service import SINGLETON_WORKSPACE_ID


def _workspace_fs(user_id: uuid.UUID | str | None = None) -> WorkspaceFsService:
    """FS handle. `user_id` → enraizado na Home do usuário; senão na raiz global
    (usado quando o caminho já é físico-relativo `{ownerId}/…`)."""
    from pathlib import Path

    settings = get_settings()
    root = Path(settings.workspace_dir)
    if user_id is not None:
        root = root / str(user_id)
        root.mkdir(parents=True, exist_ok=True)
    return WorkspaceFsService(
        root,
        max_upload_bytes=settings.workspace_max_upload_bytes,
        max_nodes=settings.workspace_tree_max_nodes,
        max_depth=settings.workspace_tree_max_depth,
    )


class WorkflowService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = WorkflowRepository(session)

    # ── CRUD ────────────────────────────────────────────────────────────────
    async def create(
        self, *, name: str, description: str | None, owner_id: uuid.UUID | None = None
    ) -> Workflow:
        workflow = Workflow(
            name=name, description=description, status=WorkflowStatus.DRAFT, owner_id=owner_id
        )
        await self.repo.add(workflow)
        return workflow

    async def get(self, workflow_id: uuid.UUID) -> Workflow:
        workflow = await self.repo.get_with_graph(workflow_id)
        if workflow is None:
            raise NotFoundError(f"Workflow {workflow_id} não encontrado.")
        return workflow

    async def get_owned(
        self, workflow_id: uuid.UUID, *, user_id: uuid.UUID, is_admin: bool
    ) -> Workflow:
        workflow = await self.get(workflow_id)
        _assert_owner(workflow, user_id=user_id, is_admin=is_admin)
        return workflow

    async def list_workflows(
        self, *, limit: int, offset: int, owner_id: uuid.UUID | None = None
    ) -> list[Workflow]:
        return await self.repo.list_paged(limit=limit, offset=offset, owner_id=owner_id)

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
        owner_id: uuid.UUID,
        is_admin: bool = False,
    ) -> Workflow:
        workflow = await self.repo.get(workflow_id)
        if workflow is None:
            raise NotFoundError(f"Workflow {workflow_id} não encontrado.")
        _assert_owner(workflow, user_id=owner_id, is_admin=is_admin)
        # o dono efetivo (para resolver a Home dos notebooks) é o do workflow
        effective_owner = workflow.owner_id or owner_id

        keys = [t.key for t in tasks]
        if len(keys) != len(set(keys)):
            raise DomainValidationError("Chaves de tarefa duplicadas no grafo.")
        key_set = set(keys)

        await self._validate_task_types(tasks, effective_owner)

        edge_keys = [(e.from_key, e.to_key) for e in dependencies]
        for src, dst in edge_keys:
            if src not in key_set or dst not in key_set:
                raise DomainValidationError("Dependência referencia tarefa fora do grafo.")
        validate_dag(key_set, edge_keys)

        existing = {t.id: t for t in await self.repo.tasks_for(workflow_id)}
        key_to_id = await self._upsert_tasks(workflow_id, tasks, existing, effective_owner)

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

        # O grafo passou na validação (todos os .ipynb existem) → se estava
        # INVALID, o usuário consertou; volta a DRAFT.
        if workflow.status == WorkflowStatus.INVALID:
            workflow.status = WorkflowStatus.DRAFT
            await self.session.flush()

        return await self.get(workflow_id)

    # ── helpers ────────────────────────────────────────────────────────────
    async def _validate_task_types(
        self, tasks: list[WorkflowTaskInput], owner_id: uuid.UUID
    ) -> None:
        legacy_notebook_ids: set[uuid.UUID] = set()
        for task in tasks:
            if task.type is not TaskType.NOTEBOOK:
                raise DomainValidationError(
                    f"Tipo de tarefa não suportado nesta fase: {task.type}."
                )
            if task.notebook_path:
                await self._validate_workspace_notebook(
                    task.name, _home_rel(task.notebook_path, owner_id), owner_id
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
        self, task_name: str, home_rel_path: str, owner_id: uuid.UUID
    ) -> None:
        if not is_ipynb(home_rel_path):
            raise DomainValidationError(
                f"Tarefa '{task_name}': o caminho deve apontar para um .ipynb."
            )
        try:
            await _workspace_fs(owner_id).read_file(home_rel_path)
        except NotFoundError as exc:
            raise DomainValidationError(
                f"Tarefa '{task_name}': notebook não encontrado em /root ({home_rel_path})."
            ) from exc

    # ── integridade de referências (rename/move/delete de notebook) ─────────
    async def repath_tasks(self, old: str, new: str, *, owner_id: uuid.UUID) -> int:
        """Reescreve `notebook_path` (físico-relativo) das tasks do usuário afetadas
        por um rename/move. `old`/`new` já vêm prefixados com `{owner_id}/`.

        Cobre o caminho exato e tudo sob ele (rename de pasta). Se um Workflow
        inválido voltar a ter todos os caminhos resolvíveis, volta a DRAFT.
        """
        rows = list(
            await self.session.scalars(
                select(WorkflowTask)
                .join(Workflow, Workflow.id == WorkflowTask.workflow_id)
                .where(
                    Workflow.owner_id == owner_id,
                    WorkflowTask.notebook_path.is_not(None),
                )
            )
        )
        changed = 0
        touched_wf: set[uuid.UUID] = set()
        for row in rows:
            p = row.notebook_path or ""
            if p == old:
                row.notebook_path = new
            elif p.startswith(f"{old}/"):
                row.notebook_path = new + p[len(old) :]
            else:
                continue
            changed += 1
            touched_wf.add(row.workflow_id)
        if changed:
            await self.session.flush()
            for wf_id in touched_wf:
                await self._revalidate_workflow(wf_id)
        return changed

    async def invalidate_referencing(self, path: str, *, owner_id: uuid.UUID) -> int:
        """Marca como INVALID os Workflows do usuário cujas tasks apontam para
        `path` (físico-relativo `{owner_id}/…`) ou algo sob ele."""
        rows = list(
            await self.session.scalars(
                select(WorkflowTask)
                .join(Workflow, Workflow.id == WorkflowTask.workflow_id)
                .where(
                    Workflow.owner_id == owner_id,
                    WorkflowTask.notebook_path.is_not(None),
                )
            )
        )
        wf_ids = {
            r.workflow_id
            for r in rows
            if (r.notebook_path == path) or (r.notebook_path or "").startswith(f"{path}/")
        }
        if not wf_ids:
            return 0
        for wf in await self.session.scalars(
            select(Workflow).where(Workflow.id.in_(wf_ids))
        ):
            if wf.status != WorkflowStatus.ARCHIVED:
                wf.status = WorkflowStatus.INVALID
        await self.session.flush()
        return len(wf_ids)

    async def _revalidate_workflow(self, workflow_id: uuid.UUID) -> None:
        """Se um Workflow INVALID tem todos os notebooks resolvíveis, volta a DRAFT."""
        wf = await self.repo.get(workflow_id)
        if wf is None or wf.status != WorkflowStatus.INVALID:
            return
        fs = _workspace_fs()  # raiz global — `notebook_path` já é físico-relativo
        for row in await self.repo.tasks_for(workflow_id):
            if not row.notebook_path:
                continue
            try:
                await fs.read_file(row.notebook_path)
            except NotFoundError:
                return
        wf.status = WorkflowStatus.DRAFT
        await self.session.flush()

    async def _upsert_tasks(
        self,
        workflow_id: uuid.UUID,
        tasks: list[WorkflowTaskInput],
        existing: dict[uuid.UUID, WorkflowTask],
        owner_id: uuid.UUID,
    ) -> dict[str, uuid.UUID]:
        key_to_id: dict[str, uuid.UUID] = {}
        for task in tasks:
            existing_id = _maybe_uuid(task.key)
            row = existing.get(existing_id) if existing_id else None
            if row is None:
                row = WorkflowTask(workflow_id=workflow_id)
                self.session.add(row)
            _apply(row, task, owner_id)
            await self.session.flush()
            key_to_id[task.key] = row.id
        return key_to_id


def _maybe_uuid(value: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(value)
    except ValueError:
        return None


def _home_rel(notebook_path: str, owner_id: uuid.UUID) -> str:
    """Tira o prefixo `{owner_id}/` se já estiver físico-relativo."""
    prefix = f"{owner_id}/"
    return notebook_path[len(prefix) :] if notebook_path.startswith(prefix) else notebook_path


def _physical(notebook_path: str, owner_id: uuid.UUID) -> str:
    """Garante o prefixo `{owner_id}/` (físico-relativo, o que vai para o DB)."""
    prefix = f"{owner_id}/"
    return notebook_path if notebook_path.startswith(prefix) else f"{prefix}{notebook_path}"


def _assert_owner(workflow: Workflow, *, user_id: uuid.UUID, is_admin: bool) -> None:
    if is_admin:
        return
    if workflow.owner_id is not None and workflow.owner_id != user_id:
        raise ForbiddenError("Workflow de outro usuário.")


def _apply(row: WorkflowTask, task: WorkflowTaskInput, owner_id: uuid.UUID) -> None:
    row.name = task.name
    row.type = task.type
    row.notebook_id = task.notebook_id
    # Isolamento por usuário: `notebook_path` persiste físico-relativo
    # (`{owner_id}/pasta/nb.ipynb`); o worker resolve contra a raiz global.
    row.workspace_id = SINGLETON_WORKSPACE_ID if task.notebook_path else task.workspace_id
    row.notebook_path = _physical(task.notebook_path, owner_id) if task.notebook_path else None
    row.parameters = task.parameters
    row.timeout_s = task.timeout_s
    row.max_retries = task.max_retries
    row.retry_policy = task.retry_policy
    row.ui_position = _position_dict(task.ui_position)


def _position_dict(pos: dict[str, float] | None) -> dict[str, Any] | None:
    if pos is None:
        return None
    return {"x": float(pos.get("x", 0)), "y": float(pos.get("y", 0))}
