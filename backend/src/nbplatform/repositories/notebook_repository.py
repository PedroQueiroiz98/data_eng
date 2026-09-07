"""Acesso a dados para Notebook / NotebookVersion."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from nbplatform.models.notebook import Notebook, NotebookVersion


class NotebookRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, notebook: Notebook) -> None:
        self.session.add(notebook)
        await self.session.flush()

    async def get(self, notebook_id: uuid.UUID) -> Notebook | None:
        return await self.session.get(Notebook, notebook_id)

    async def get_for_update(self, notebook_id: uuid.UUID) -> Notebook | None:
        stmt = select(Notebook).where(Notebook.id == notebook_id).with_for_update()
        return await self.session.scalar(stmt)

    async def list_paged(self, *, limit: int, offset: int) -> list[Notebook]:
        stmt = (
            select(Notebook)
            .order_by(Notebook.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(await self.session.scalars(stmt))

    async def delete(self, notebook: Notebook) -> None:
        await self.session.delete(notebook)

    async def add_version(self, version: NotebookVersion) -> None:
        self.session.add(version)
        await self.session.flush()

    async def get_version_by_id(self, version_id: uuid.UUID) -> NotebookVersion | None:
        return await self.session.get(NotebookVersion, version_id)

    async def get_version(
        self, notebook_id: uuid.UUID, version_number: int
    ) -> NotebookVersion | None:
        stmt = select(NotebookVersion).where(
            NotebookVersion.notebook_id == notebook_id,
            NotebookVersion.version_number == version_number,
        )
        return await self.session.scalar(stmt)

    async def list_versions(self, notebook_id: uuid.UUID) -> list[NotebookVersion]:
        stmt = (
            select(NotebookVersion)
            .where(NotebookVersion.notebook_id == notebook_id)
            .order_by(NotebookVersion.version_number.desc())
        )
        return list(await self.session.scalars(stmt))

    async def count_versions(self, notebook_id: uuid.UUID) -> int:
        stmt = select(func.count()).select_from(NotebookVersion).where(
            NotebookVersion.notebook_id == notebook_id
        )
        return int(await self.session.scalar(stmt) or 0)

    async def max_version_number(self, notebook_id: uuid.UUID) -> int:
        stmt = select(func.max(NotebookVersion.version_number)).where(
            NotebookVersion.notebook_id == notebook_id
        )
        return int(await self.session.scalar(stmt) or 0)
