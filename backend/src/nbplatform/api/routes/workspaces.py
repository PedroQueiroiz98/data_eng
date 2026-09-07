"""Endpoints de Workspace: CRUD + File Explorer."""

from __future__ import annotations

import io
import uuid
from collections.abc import Iterator
from pathlib import Path

from fastapi import APIRouter, File, Query, UploadFile, status
from fastapi.responses import Response, StreamingResponse

from nbplatform.api.deps import AdminUser, CurrentUserId, SessionDep
from nbplatform.core.config import get_settings
from nbplatform.schemas.workspace import (
    CopyRequest,
    FileContentRead,
    FileNode,
    RenameRequest,
    WorkspaceCreate,
    WorkspaceDetail,
    WorkspaceRead,
    WorkspaceUpdate,
    WriteFileRequest,
)
from nbplatform.services.audit_service import AuditService
from nbplatform.services.workspace_fs_service import WorkspaceFsService
from nbplatform.services.workspace_service import WorkspaceService

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])


def _fs(svc: WorkspaceService, workspace_id: uuid.UUID) -> WorkspaceFsService:
    settings = get_settings()
    return WorkspaceFsService(
        svc.root_for(workspace_id),
        max_upload_bytes=settings.workspace_max_upload_bytes,
        max_nodes=settings.workspace_tree_max_nodes,
        max_depth=settings.workspace_tree_max_depth,
    )


async def _audit(
    session: SessionDep, user_id: uuid.UUID, action: str, wid: uuid.UUID, **meta: object
) -> None:
    await AuditService(session).record(
        user_id=user_id,
        action=action,
        resource_type="workspace",
        resource_id=str(wid),
        metadata={k: str(v) for k, v in meta.items()} or None,
    )


# ── Workspace CRUD ──────────────────────────────────────────────────────────
@router.get("", response_model=list[WorkspaceRead])
async def list_workspaces(
    session: SessionDep,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    include_inactive: bool = Query(default=False),
) -> list[WorkspaceRead]:
    rows = await WorkspaceService(session).list_workspaces(
        limit=limit, offset=offset, include_inactive=include_inactive
    )
    return [WorkspaceRead.model_validate(w) for w in rows]


@router.post("", response_model=WorkspaceDetail, status_code=status.HTTP_201_CREATED)
async def create_workspace(
    payload: WorkspaceCreate, session: SessionDep, admin: AdminUser
) -> WorkspaceDetail:
    svc = WorkspaceService(session)
    workspace = await svc.create(
        name=payload.name, description=payload.description, owner_id=admin.id
    )
    await _audit(session, admin.id, "CREATE_WORKSPACE", workspace.id, name=workspace.name)
    return WorkspaceDetail.model_validate(workspace)


@router.get("/{workspace_id}", response_model=WorkspaceDetail)
async def get_workspace(workspace_id: uuid.UUID, session: SessionDep) -> WorkspaceDetail:
    workspace = await WorkspaceService(session).get(workspace_id)
    return WorkspaceDetail.model_validate(workspace)


@router.patch("/{workspace_id}", response_model=WorkspaceDetail)
async def update_workspace(
    workspace_id: uuid.UUID,
    payload: WorkspaceUpdate,
    session: SessionDep,
    admin: AdminUser,
) -> WorkspaceDetail:
    svc = WorkspaceService(session)
    workspace = await svc.update(
        workspace_id,
        name=payload.name,
        description=payload.description,
        is_active=payload.is_active,
    )
    await _audit(session, admin.id, "UPDATE_WORKSPACE", workspace_id)
    return WorkspaceDetail.model_validate(workspace)


@router.delete("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workspace(
    workspace_id: uuid.UUID,
    session: SessionDep,
    admin: AdminUser,
    purge: bool = Query(default=False),
) -> None:
    await WorkspaceService(session).delete(workspace_id, purge=purge)
    await _audit(
        session, admin.id, "DELETE_WORKSPACE", workspace_id, purge=purge
    )


# ── File Explorer ──────────────────────────────────────────────────────────
@router.get("/{workspace_id}/tree", response_model=FileNode)
async def get_tree(
    workspace_id: uuid.UUID,
    session: SessionDep,
    path: str = Query(default=""),
    depth: int | None = Query(default=None, ge=1, le=64),
) -> FileNode:
    svc = WorkspaceService(session)
    await svc.get(workspace_id)
    tree = await _fs(svc, workspace_id).list_tree(rel_path=path, depth=depth)
    return FileNode.model_validate(tree, from_attributes=True)


@router.get("/{workspace_id}/file", response_model=FileContentRead)
async def read_file(
    workspace_id: uuid.UUID, session: SessionDep, path: str = Query(min_length=1)
) -> FileContentRead:
    svc = WorkspaceService(session)
    await svc.get(workspace_id)
    content = await _fs(svc, workspace_id).read_file(path)
    return FileContentRead.model_validate(content, from_attributes=True)


@router.put("/{workspace_id}/file", response_model=FileContentRead)
async def write_file(
    workspace_id: uuid.UUID,
    payload: WriteFileRequest,
    session: SessionDep,
    user_id: CurrentUserId,
    path: str = Query(min_length=1),
) -> FileContentRead:
    svc = WorkspaceService(session)
    await svc.get_active(workspace_id)
    content = await _fs(svc, workspace_id).write_file(
        path, text=payload.text, notebook=payload.notebook
    )
    await _audit(session, user_id, "WORKSPACE_FS_WRITE", workspace_id, path=path)
    return FileContentRead.model_validate(content, from_attributes=True)


@router.post(
    "/{workspace_id}/dir", response_model=FileNode, status_code=status.HTTP_201_CREATED
)
async def make_dir(
    workspace_id: uuid.UUID,
    session: SessionDep,
    user_id: CurrentUserId,
    path: str = Query(min_length=1),
) -> FileNode:
    svc = WorkspaceService(session)
    await svc.get_active(workspace_id)
    node = await _fs(svc, workspace_id).make_dir(path)
    await _audit(session, user_id, "WORKSPACE_FS_MKDIR", workspace_id, path=path)
    return FileNode.model_validate(node, from_attributes=True)


@router.delete("/{workspace_id}/file", status_code=status.HTTP_204_NO_CONTENT)
async def delete_entry(
    workspace_id: uuid.UUID,
    session: SessionDep,
    user_id: CurrentUserId,
    path: str = Query(min_length=1),
    recursive: bool = Query(default=False),
) -> None:
    svc = WorkspaceService(session)
    await svc.get_active(workspace_id)
    await _fs(svc, workspace_id).delete(path, recursive=recursive)
    await _audit(session, user_id, "WORKSPACE_FS_DELETE", workspace_id, path=path)


@router.post("/{workspace_id}/rename", response_model=FileNode)
async def rename_entry(
    workspace_id: uuid.UUID,
    payload: RenameRequest,
    session: SessionDep,
    user_id: CurrentUserId,
) -> FileNode:
    svc = WorkspaceService(session)
    await svc.get_active(workspace_id)
    node = await _fs(svc, workspace_id).rename(payload.src, payload.dst)
    await _audit(
        session, user_id, "WORKSPACE_FS_RENAME", workspace_id,
        src=payload.src, dst=payload.dst,
    )
    return FileNode.model_validate(node, from_attributes=True)


@router.post("/{workspace_id}/copy", response_model=FileNode)
async def copy_entry(
    workspace_id: uuid.UUID,
    payload: CopyRequest,
    session: SessionDep,
    user_id: CurrentUserId,
) -> FileNode:
    svc = WorkspaceService(session)
    await svc.get_active(workspace_id)
    node = await _fs(svc, workspace_id).copy(payload.src, payload.dst)
    await _audit(
        session, user_id, "WORKSPACE_FS_COPY", workspace_id,
        src=payload.src, dst=payload.dst,
    )
    return FileNode.model_validate(node, from_attributes=True)


@router.post(
    "/{workspace_id}/upload", response_model=FileNode, status_code=status.HTTP_201_CREATED
)
async def upload_file(
    workspace_id: uuid.UUID,
    session: SessionDep,
    user_id: CurrentUserId,
    file: UploadFile = File(...),
    path: str = Query(default=""),
) -> FileNode:
    svc = WorkspaceService(session)
    await svc.get_active(workspace_id)
    node = await _fs(svc, workspace_id).save_upload(
        path, file.filename or "arquivo", file
    )
    await _audit(
        session, user_id, "WORKSPACE_FS_UPLOAD", workspace_id, path=node.path
    )
    return FileNode.model_validate(node, from_attributes=True)


@router.get("/{workspace_id}/download")
async def download(
    workspace_id: uuid.UUID, session: SessionDep, path: str = Query(min_length=1)
) -> Response:
    svc = WorkspaceService(session)
    await svc.get(workspace_id)
    source, name, is_zip = await _fs(svc, workspace_id).open_download(path)
    media = "application/zip" if is_zip else "application/octet-stream"
    headers = {"Content-Disposition": f'attachment; filename="{name}"'}

    if isinstance(source, io.BytesIO):
        return StreamingResponse(iter([source.getvalue()]), media_type=media, headers=headers)

    file_path = Path(source)

    def _iter() -> Iterator[bytes]:
        with file_path.open("rb") as fh:
            while chunk := fh.read(1024 * 1024):
                yield chunk

    return StreamingResponse(_iter(), media_type=media, headers=headers)
