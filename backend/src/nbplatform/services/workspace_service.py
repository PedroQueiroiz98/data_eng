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
from nbplatform.core.errors import ConflictError, NotFoundError
from nbplatform.domain.enums import ExecutionStatus
from nbplatform.domain.workspace_layout import (
    GITIGNORE_TEXT,
    SKELETON_DIRS,
    build_workspace_json,
    dump_workspace_json,
    slugify,
)
from nbplatform.models.execution import Execution
from nbplatform.models.workspace import Workspace
from nbplatform.repositories.workspace_repository import WorkspaceRepository

_SLUG_ATTEMPTS = 50


class WorkspaceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = WorkspaceRepository(session)
        self.settings = get_settings()

    def root_for(self, workspace_id: uuid.UUID) -> Path:
        return Path(self.settings.workspaces_dir) / str(workspace_id)

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
        self, *, limit: int, offset: int, include_inactive: bool
    ) -> list[Workspace]:
        return await self.repo.list_paged(
            limit=limit, offset=offset, include_inactive=include_inactive
        )

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
                Execution.status.in_(
                    [ExecutionStatus.QUEUED, ExecutionStatus.RUNNING]
                ),
            )
        )
        if active:
            raise ConflictError(
                "Workspace tem execuções em andamento; aguarde ou cancele antes de excluir."
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


def _provision_tree(
    root: Path, *, workspace_id: str, name: str, slug: str, created_at: str
) -> None:
    for d in SKELETON_DIRS:
        (root / d).mkdir(parents=True, exist_ok=True)
    (root / ".gitignore").write_text(GITIGNORE_TEXT, encoding="utf-8")
    meta = build_workspace_json(
        workspace_id=workspace_id, name=name, slug=slug, created_at=created_at
    )
    (root / ".workspace" / "workspace.json").write_text(
        dump_workspace_json(meta), encoding="utf-8"
    )


def _rmtree_silent(path: Path) -> None:
    with contextlib.suppress(FileNotFoundError):
        shutil.rmtree(path)
