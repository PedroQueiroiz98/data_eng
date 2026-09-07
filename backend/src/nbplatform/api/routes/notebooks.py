"""Endpoints de Notebook (metadados + versões imutáveis)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, status

from nbplatform.api.deps import CurrentUserId, SessionDep
from nbplatform.schemas.notebook import (
    NotebookContentSave,
    NotebookCreate,
    NotebookDetail,
    NotebookRead,
    NotebookUpdate,
    NotebookVersionDetail,
    NotebookVersionRead,
)
from nbplatform.services.notebook_service import NotebookService

router = APIRouter(prefix="/api/notebooks", tags=["notebooks"])


async def _detail(service: NotebookService, notebook_id: uuid.UUID) -> NotebookDetail:
    notebook = await service.get(notebook_id)
    detail = NotebookDetail.model_validate(notebook)
    detail.content = await service.current_content(notebook)
    detail.version_count = await service.version_count(notebook_id)
    return detail


@router.get("", response_model=list[NotebookRead])
async def list_notebooks(
    session: SessionDep,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[NotebookRead]:
    notebooks = await NotebookService(session).list_notebooks(limit=limit, offset=offset)
    return [NotebookRead.model_validate(n) for n in notebooks]


@router.post("", response_model=NotebookDetail, status_code=status.HTTP_201_CREATED)
async def create_notebook(
    payload: NotebookCreate, session: SessionDep, user_id: CurrentUserId
) -> NotebookDetail:
    service = NotebookService(session)
    notebook = await service.create(
        name=payload.name,
        description=payload.description,
        content=payload.content,
        created_by=user_id,
    )
    await session.flush()
    return await _detail(service, notebook.id)


@router.get("/{notebook_id}", response_model=NotebookDetail)
async def get_notebook(notebook_id: uuid.UUID, session: SessionDep) -> NotebookDetail:
    return await _detail(NotebookService(session), notebook_id)


@router.put("/{notebook_id}", response_model=NotebookDetail)
async def update_notebook(
    notebook_id: uuid.UUID, payload: NotebookUpdate, session: SessionDep
) -> NotebookDetail:
    service = NotebookService(session)
    await service.update_metadata(
        notebook_id, name=payload.name, description=payload.description
    )
    return await _detail(service, notebook_id)


@router.delete("/{notebook_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notebook(notebook_id: uuid.UUID, session: SessionDep) -> None:
    await NotebookService(session).delete(notebook_id)


@router.post(
    "/{notebook_id}/versions",
    response_model=NotebookVersionDetail,
    status_code=status.HTTP_201_CREATED,
)
async def save_version(
    notebook_id: uuid.UUID,
    payload: NotebookContentSave,
    session: SessionDep,
    user_id: CurrentUserId,
) -> NotebookVersionDetail:
    version = await NotebookService(session).save_version(
        notebook_id, content=payload.content, created_by=user_id
    )
    await session.flush()
    return NotebookVersionDetail.model_validate(version)


@router.get("/{notebook_id}/versions", response_model=list[NotebookVersionRead])
async def list_versions(
    notebook_id: uuid.UUID, session: SessionDep
) -> list[NotebookVersionRead]:
    versions = await NotebookService(session).list_versions(notebook_id)
    return [NotebookVersionRead.model_validate(v) for v in versions]


@router.get(
    "/{notebook_id}/versions/{version_number}", response_model=NotebookVersionDetail
)
async def get_version(
    notebook_id: uuid.UUID, version_number: int, session: SessionDep
) -> NotebookVersionDetail:
    version = await NotebookService(session).get_version(notebook_id, version_number)
    return NotebookVersionDetail.model_validate(version)
