"""Regras de negócio de Workspace: CRUD + provisionamento do filesystem."""

from __future__ import annotations

import asyncio
import contextlib
import shutil
import uuid
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import set_committed_value

from nbplatform.core.config import get_settings
from nbplatform.core.errors import ConflictError, DomainValidationError, NotFoundError
from nbplatform.db.session import session_scope
from nbplatform.domain.enums import ExecutionStatus, WorkspaceRole
from nbplatform.domain.workspace_layout import (
    build_workspace_json,
    dump_workspace_json,
    slugify,
)
from nbplatform.models.execution import Execution
from nbplatform.models.workflow import WorkflowTask
from nbplatform.models.workspace import Workspace, WorkspaceMember
from nbplatform.repositories.workspace_repository import WorkspaceRepository

_SLUG_ATTEMPTS = 50

# Modo single-workspace: um único Workspace com UUID fixo. A raiz física é
# `settings.workspace_dir` e a UI a mostra como `/root`.
SINGLETON_WORKSPACE_ID = uuid.UUID("00000000-0000-0000-0000-0000000000a1")


class WorkspaceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = WorkspaceRepository(session)
        self.settings = get_settings()

    @property
    def root_dir(self) -> Path:
        return Path(self.settings.workspace_dir)

    def root_for(self, workspace_id: uuid.UUID | None = None) -> Path:
        # Single-workspace: a raiz é sempre `workspace_dir` (o id é ignorado).
        return self.root_dir

    # ── single workspace ────────────────────────────────────────────────────
    async def get_singleton(self) -> Workspace:
        ws = await self.repo.get(SINGLETON_WORKSPACE_ID)
        if ws is None:
            ws = await self._create_singleton()
        return ws

    async def get_singleton_active(self) -> Workspace:
        return await self.get_singleton()

    async def _create_singleton(self) -> Workspace:
        root = self.root_dir
        ws = Workspace(
            id=SINGLETON_WORKSPACE_ID,
            name="Workspace",
            slug="root",
            description=None,
            owner_id=None,
            root_path=str(root),
            is_active=True,
        )
        try:
            await self.repo.add(ws)
        except IntegrityError:
            await self.session.rollback()
            got = await self.repo.get(SINGLETON_WORKSPACE_ID)
            if got is not None:
                return got
            raise
        set_committed_value(ws, "git_repository", None)
        set_committed_value(ws, "members", [])
        await self.session.flush()
        await asyncio.to_thread(_provision_root, root, ws.created_at.isoformat())
        return ws

    # ── CRUD ─────────────────────────────────────────────────────────────────
    async def create(
        self, *, name: str, description: str | None, owner_id: uuid.UUID | None
    ) -> Workspace:
        workspace_id = uuid.uuid4()
        root = self.root_for(workspace_id)
        slug = await self._unique_slug(slugify(name))

        workspace = Workspace(
            id=workspace_id,
            name=name,
            slug=slug,
            description=description,
            owner_id=owner_id,
            root_path=str(root),
            is_active=True,
        )
        try:
            await self.repo.add(workspace)
        except IntegrityError:
            await self.session.rollback()
            raise ConflictError("Slug de Workspace já em uso; tente outro nome.") from None

        # Recém-criado nunca tem repositório Git; marca o relacionamento como
        # carregado para o model_validate não disparar lazy-load (async).
        set_committed_value(workspace, "git_repository", None)
        await self.session.flush()

        # O criador vira OWNER (ACL). Admin global tem bypass, mas registrar o
        # vínculo mantém a listagem por membro consistente.
        if owner_id is not None:
            self.session.add(
                WorkspaceMember(
                    workspace_id=workspace_id,
                    user_id=owner_id,
                    role=WorkspaceRole.OWNER,
                )
            )
            await self.session.flush()

        await asyncio.to_thread(
            _provision_tree,
            root,
            workspace_id=str(workspace_id),
            name=name,
            slug=slug,
            created_at=workspace.created_at.isoformat(),
        )
        return workspace

    async def get(self, workspace_id: uuid.UUID) -> Workspace:
        workspace = await self.repo.get(workspace_id)
        if workspace is None:
            raise NotFoundError(f"Workspace {workspace_id} não encontrado.")
        return workspace

    async def get_active(self, workspace_id: uuid.UUID) -> Workspace:
        workspace = await self.get(workspace_id)
        if not workspace.is_active:
            raise ConflictError("Workspace inativo.")
        return workspace

    async def list_workspaces(
        self,
        *,
        limit: int,
        offset: int,
        include_inactive: bool,
        member_user_id: uuid.UUID | None = None,
    ) -> list[Workspace]:
        return await self.repo.list_paged(
            limit=limit,
            offset=offset,
            include_inactive=include_inactive,
            member_user_id=member_user_id,
        )

    # ── membros (ACL) ────────────────────────────────────────────────────────
    async def list_members(self, workspace_id: uuid.UUID) -> list[WorkspaceMember]:
        await self.get(workspace_id)
        return await self.repo.list_members(workspace_id)

    async def set_member(
        self, workspace_id: uuid.UUID, user_id: uuid.UUID, role: WorkspaceRole
    ) -> WorkspaceMember:
        await self.get(workspace_id)
        existing = await self.repo.get_member(workspace_id, user_id)
        # Rebaixar o último OWNER deixaria o Workspace sem dono.
        if (
            existing is not None
            and existing.role == WorkspaceRole.OWNER
            and role != WorkspaceRole.OWNER
            and await self.repo.count_owners(workspace_id) <= 1
        ):
            raise DomainValidationError("O Workspace precisa de ao menos um OWNER.")
        return await self.repo.upsert_member(workspace_id, user_id, role)

    async def remove_member(self, workspace_id: uuid.UUID, user_id: uuid.UUID) -> None:
        await self.get(workspace_id)
        member = await self.repo.get_member(workspace_id, user_id)
        if member is None:
            raise NotFoundError("Membro não encontrado neste Workspace.")
        if member.role == WorkspaceRole.OWNER and await self.repo.count_owners(workspace_id) <= 1:
            raise DomainValidationError("Não é possível remover o único OWNER do Workspace.")
        await self.repo.remove_member(member)

    async def update(
        self,
        workspace_id: uuid.UUID,
        *,
        name: str | None,
        description: str | None,
        is_active: bool | None,
    ) -> Workspace:
        workspace = await self.get(workspace_id)
        if name is not None:
            workspace.name = name
        if description is not None:
            workspace.description = description
        if is_active is not None:
            workspace.is_active = is_active
        await self.session.flush()
        # `updated_at` tem onupdate=func.now(): o flush o expira e a leitura
        # síncrona (pydantic) dispararia lazy IO fora do greenlet → refresh aqui.
        await self.session.refresh(workspace, attribute_names=["updated_at"])
        return workspace

    async def delete(self, workspace_id: uuid.UUID, *, purge: bool) -> None:
        workspace = await self.get(workspace_id)
        if not purge:
            workspace.is_active = False
            await self.session.flush()
            return

        active = await self.session.scalar(
            select(func.count())
            .select_from(Execution)
            .where(
                Execution.workspace_id == workspace_id,
                Execution.status.in_([ExecutionStatus.QUEUED, ExecutionStatus.RUNNING]),
            )
        )
        if active:
            raise ConflictError(
                "Workspace tem execuções em andamento; aguarde ou cancele antes de excluir."
            )

        # `executions.workspace_id` e `workflow_tasks.workspace_id` são FKs
        # `ON DELETE RESTRICT` (proveniência). Sem esta checagem o DELETE explode
        # num IntegrityError 500 — devolvemos um 409 claro e orientamos o
        # soft-delete (que apenas inativa o Workspace).
        hist_exec = await self.session.scalar(
            select(func.count())
            .select_from(Execution)
            .where(Execution.workspace_id == workspace_id)
        )
        hist_task = await self.session.scalar(
            select(func.count())
            .select_from(WorkflowTask)
            .where(WorkflowTask.workspace_id == workspace_id)
        )
        if hist_exec or hist_task:
            raise ConflictError(
                "Workspace tem histórico de execuções/workflows e não pode ser "
                "removido permanentemente (proveniência). Use a exclusão simples "
                "(sem purge), que apenas o inativa."
            )

        root = Path(workspace.root_path)
        await self.repo.delete(workspace)
        await asyncio.to_thread(_rmtree_silent, root)

    # ── helpers ──────────────────────────────────────────────────────────────
    async def _unique_slug(self, base: str) -> str:
        for i in range(_SLUG_ATTEMPTS):
            candidate = base if i == 0 else f"{base}-{i + 1}"
            if await self.repo.get_by_slug(candidate) is None:
                return candidate
        return f"{base}-{uuid.uuid4().hex[:8]}"


def _provision_root(root: Path, created_at: str) -> None:
    """Cria a raiz do Workspace único VAZIA (sem skeleton, sem .gitignore).

    Só o `.workspace/workspace.json` interno é escrito (oculto no File Explorer).
    """
    root.mkdir(parents=True, exist_ok=True)
    (root / ".workspace").mkdir(parents=True, exist_ok=True)
    meta = build_workspace_json(
        workspace_id=str(SINGLETON_WORKSPACE_ID), name="Workspace", slug="root",
        created_at=created_at,
    )
    (root / ".workspace" / "workspace.json").write_text(
        dump_workspace_json(meta), encoding="utf-8"
    )


def _provision_tree(
    root: Path, *, workspace_id: str, name: str, slug: str, created_at: str
) -> None:
    # Legado (rota de criação de Workspace foi removida no modo single-workspace);
    # mantido só por compat. NÃO cria mais skeleton — raiz começa vazia.
    _provision_root(root, created_at)


def _rmtree_silent(path: Path) -> None:
    with contextlib.suppress(FileNotFoundError):
        shutil.rmtree(path)


async def ensure_singleton_workspace() -> None:
    """Startup: garante que o Workspace único exista (idempotente)."""
    settings = get_settings()
    root = Path(settings.workspace_dir)
    await asyncio.to_thread(_ensure_root_dir, root)
    async with session_scope() as session:
        await WorkspaceService(session).get_singleton()


def _ensure_root_dir(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    internal = root / ".workspace"
    internal.mkdir(parents=True, exist_ok=True)
    meta_file = internal / "workspace.json"
    if not meta_file.exists():
        meta = build_workspace_json(
            workspace_id=str(SINGLETON_WORKSPACE_ID),
            name="Workspace",
            slug="root",
            created_at="",
        )
        meta_file.write_text(dump_workspace_json(meta), encoding="utf-8")
