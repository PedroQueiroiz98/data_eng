"""Acesso a dados para Workspace / WorkspaceGitRepository / WorkspaceMember."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from nbplatform.domain.enums import WorkspaceRole
from nbplatform.models.workspace import Workspace, WorkspaceMember


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
        self,
        *,
        limit: int,
        offset: int,
        include_inactive: bool,
        member_user_id: uuid.UUID | None = None,
    ) -> list[Workspace]:
        stmt = (
            select(Workspace)
            .options(selectinload(Workspace.git_repository))
            .order_by(Workspace.updated_at.desc())
        )
        if not include_inactive:
            stmt = stmt.where(Workspace.is_active.is_(True))
        if member_user_id is not None:
            stmt = stmt.where(
                Workspace.id.in_(
                    select(WorkspaceMember.workspace_id).where(
                        WorkspaceMember.user_id == member_user_id
                    )
                )
            )
        stmt = stmt.limit(limit).offset(offset)
        return list(await self.session.scalars(stmt))

    async def delete(self, workspace: Workspace) -> None:
        await self.session.delete(workspace)
        await self.session.flush()

    # ── membros (ACL) ────────────────────────────────────────────────────────
    async def get_member(
        self, workspace_id: uuid.UUID, user_id: uuid.UUID
    ) -> WorkspaceMember | None:
        return await self.session.scalar(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == user_id,
            )
        )

    async def list_members(self, workspace_id: uuid.UUID) -> list[WorkspaceMember]:
        return list(
            await self.session.scalars(
                select(WorkspaceMember)
                .where(WorkspaceMember.workspace_id == workspace_id)
                .order_by(WorkspaceMember.created_at)
            )
        )

    async def count_owners(self, workspace_id: uuid.UUID) -> int:
        rows = await self.session.scalars(
            select(WorkspaceMember.id).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.role == WorkspaceRole.OWNER,
            )
        )
        return len(list(rows))

    async def upsert_member(
        self, workspace_id: uuid.UUID, user_id: uuid.UUID, role: WorkspaceRole
    ) -> WorkspaceMember:
        member = await self.get_member(workspace_id, user_id)
        if member is None:
            member = WorkspaceMember(
                workspace_id=workspace_id, user_id=user_id, role=role
            )
            self.session.add(member)
        else:
            member.role = role
        await self.session.flush()
        return member

    async def remove_member(self, member: WorkspaceMember) -> None:
        await self.session.delete(member)
        await self.session.flush()
