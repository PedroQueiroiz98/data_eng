"""Regras de negócio de Notebook: CRUD de metadados + versionamento imutável."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from nbplatform.core.errors import NotFoundError
from nbplatform.domain.notebook_format import new_empty_notebook, validate_notebook
from nbplatform.models.notebook import Notebook, NotebookVersion
from nbplatform.repositories.notebook_repository import NotebookRepository


class NotebookService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = NotebookRepository(session)

    # ── Metadados ────────────────────────────────────────────────────────────
    async def create(
        self,
        *,
        name: str,
        description: str | None,
        content: dict[str, Any] | None,
        created_by: uuid.UUID | None,
    ) -> Notebook:
        validated = validate_notebook(content) if content is not None else new_empty_notebook()

        notebook = Notebook(
            name=name, description=description, created_by=created_by, current_version=1
        )
        await self.repo.add(notebook)

        version = NotebookVersion(
            notebook_id=notebook.id,
            version_number=1,
            content=validated,
            created_by=created_by,
        )
        await self.repo.add_version(version)
        return notebook

    async def get(self, notebook_id: uuid.UUID) -> Notebook:
        notebook = await self.repo.get(notebook_id)
        if notebook is None:
            raise NotFoundError(f"Notebook {notebook_id} não encontrado.")
        return notebook

    async def list_notebooks(self, *, limit: int, offset: int) -> list[Notebook]:
        return await self.repo.list_paged(limit=limit, offset=offset)

    async def update_metadata(
        self, notebook_id: uuid.UUID, *, name: str | None, description: str | None
    ) -> Notebook:
        notebook = await self.get(notebook_id)
        if name is not None:
            notebook.name = name
        if description is not None:
            notebook.description = description
        await self.session.flush()
        return notebook

    async def delete(self, notebook_id: uuid.UUID) -> None:
        notebook = await self.get(notebook_id)
        await self.repo.delete(notebook)

    # ── Versionamento (imutável) ─────────────────────────────────────────────
    async def save_version(
        self, notebook_id: uuid.UUID, *, content: dict[str, Any], created_by: uuid.UUID | None
    ) -> NotebookVersion:
        validated = validate_notebook(content)

        # Lock na linha do notebook: serializa saves concorrentes e protege o
        # cálculo de version_number.
        notebook = await self.repo.get_for_update(notebook_id)
        if notebook is None:
            raise NotFoundError(f"Notebook {notebook_id} não encontrado.")

        next_number = await self.repo.max_version_number(notebook_id) + 1
        version = NotebookVersion(
            notebook_id=notebook_id,
            version_number=next_number,
            content=validated,
            created_by=created_by,
        )
        await self.repo.add_version(version)
        notebook.current_version = next_number
        await self.session.flush()
        return version

    async def get_version(
        self, notebook_id: uuid.UUID, version_number: int
    ) -> NotebookVersion:
        version = await self.repo.get_version(notebook_id, version_number)
        if version is None:
            raise NotFoundError(
                f"Versão {version_number} do notebook {notebook_id} não encontrada."
            )
        return version

    async def list_versions(self, notebook_id: uuid.UUID) -> list[NotebookVersion]:
        await self.get(notebook_id)  # 404 se o notebook não existe
        return await self.repo.list_versions(notebook_id)

    async def current_content(self, notebook: Notebook) -> dict[str, Any] | None:
        version = await self.repo.get_version(notebook.id, notebook.current_version)
        return version.content if version else None

    async def version_count(self, notebook_id: uuid.UUID) -> int:
        return await self.repo.count_versions(notebook_id)
