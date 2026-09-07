"""Acesso a dados para Workspace / WorkspaceGitRepository."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from nbplatform.models.workspace import Workspace


class WorkspaceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, workspace: Workspace) -> None:
        self.session.add(workspace)
        await self.session.flush()

    async def get(self, workspace_id: uuid.UUID) -> Workspace | None:
        stmt = (
            select(Workspace)
            .where(Workspace.id == workspace_id)
            .options(selectinload(Workspace.git_repository))
        )
        return await self.session.scalar(stmt)

    async def get_for_update(self, workspace_id: uuid.UUID) -> Workspace | None:
        stmt = select(Workspace).where(Workspace.id == workspace_id).with_for_update()
        return await self.session.scalar(stmt)

    async def get_by_slug(self, slug: str) -> Workspace | None:
        return await self.session.scalar(select(Workspace).where(Workspace.slug == slug))

    async def list_paged(
        self, *, limit: int, offset: int, include_inactive: bool
    ) -> list[Workspace]:
        stmt = (
            select(Workspace)
            .options(selectinload(Workspace.git_repository))
            .order_by(Workspace.updated_at.desc())
        )
        if not include_inactive:
            stmt = stmt.where(Workspace.is_active.is_(True))
        stmt = stmt.limit(limit).offset(offset)
        return list(await self.session.scalars(stmt))

    async def delete(self, workspace: Workspace) -> None:
        await self.session.delete(workspace)
        await self.session.flush()
