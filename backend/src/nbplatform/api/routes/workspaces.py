"""Endpoints de Workspace: CRUD + File Explorer + ACL de membros.

Autorização (além do JWT):
- listar/ler árvore/ler arquivo/baixar  → VIEWER (membro) ou admin global
- escrever/criar/remover/renomear/copiar/upload → EDITOR
- criar Workspace → admin global
- editar/excluir Workspace, gerenciar membros → OWNER
"""

from __future__ import annotations

import io
import logging
import uuid
from collections.abc import Iterator
from pathlib import Path

from fastapi import APIRouter, File, Header, Query, UploadFile, status
from fastapi.responses import Response, StreamingResponse

from nbplatform.api.deps import (
    AdminUser,
    CurrentUser,
    RedisDep,
    SessionDep,
    WorkspaceEditor,
    WorkspaceOwner,
    WorkspaceViewer,
)
from nbplatform.core.config import get_settings
from nbplatform.core.errors import DomainValidationError
from nbplatform.domain.enums import WorkspaceRole
from nbplatform.domain.workspace_paths import is_ipynb
from nbplatform.queue.execution_queue import ExecutionQueue
from nbplatform.schemas.execution import ExecutionRead
from nbplatform.schemas.workspace import (
    CopyRequest,
    DataPreviewRead,
    FileContentRead,
    FileNode,
    FilePathsRead,
    GenerateFileRequest,
    RenameRequest,
    WorkspaceCreate,
    WorkspaceDetail,
    WorkspaceExecuteRequest,
    WorkspaceMemberRead,
    WorkspaceMemberUpsert,
    WorkspaceRead,
    WorkspaceUpdate,
    WriteFileRequest,
)
from nbplatform.services.audit_service import AuditService
from nbplatform.services.execution_service import ExecutionService
from nbplatform.services.workspace_fs_service import WorkspaceFsService
from nbplatform.services.workspace_service import WorkspaceService

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])
logger = logging.getLogger("nbplatform.workspace.fs")


def _log_op(
    operation: str,
    *,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    status_: str = "SUCCESS",
    **paths: str | None,
) -> None:
    """Log estruturado de operação de arquivo do Workspace (ver report §51)."""
    logger.info(
        "workspace file operation",
        extra={
            "operation": operation,
            "workspace_id": str(workspace_id),
            "user_id": str(user_id),
            "status": status_,
            **{k: v for k, v in paths.items() if v is not None},
        },
    )


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
    user: CurrentUser,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    include_inactive: bool = Query(default=False),
) -> list[WorkspaceRead]:
    # admin global vê tudo; demais, só os Workspaces onde são membros.
    member_filter = None if user.role == "admin" else user.id
    rows = await WorkspaceService(session).list_workspaces(
        limit=limit,
        offset=offset,
        include_inactive=include_inactive,
        member_user_id=member_filter,
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
async def get_workspace(
    workspace_id: uuid.UUID, session: SessionDep, _access: WorkspaceViewer
) -> WorkspaceDetail:
    workspace = await WorkspaceService(session).get(workspace_id)
    return WorkspaceDetail.model_validate(workspace)


@router.patch("/{workspace_id}", response_model=WorkspaceDetail)
async def update_workspace(
    workspace_id: uuid.UUID,
    payload: WorkspaceUpdate,
    session: SessionDep,
    access: WorkspaceOwner,
) -> WorkspaceDetail:
    svc = WorkspaceService(session)
    workspace = await svc.update(
        workspace_id,
        name=payload.name,
        description=payload.description,
        is_active=payload.is_active,
    )
    await _audit(session, access.user.id, "UPDATE_WORKSPACE", workspace_id)
    return WorkspaceDetail.model_validate(workspace)


@router.delete("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workspace(
    workspace_id: uuid.UUID,
    session: SessionDep,
    access: WorkspaceOwner,
    purge: bool = Query(default=False),
) -> None:
    await WorkspaceService(session).delete(workspace_id, purge=purge)
    await _audit(session, access.user.id, "DELETE_WORKSPACE", workspace_id, purge=purge)


# ── Membros (ACL) ──────────────────────────────────────────────────────────
@router.get("/{workspace_id}/members", response_model=list[WorkspaceMemberRead])
async def list_members(
    workspace_id: uuid.UUID, session: SessionDep, _access: WorkspaceViewer
) -> list[WorkspaceMemberRead]:
    rows = await WorkspaceService(session).list_members(workspace_id)
    return [WorkspaceMemberRead.model_validate(m) for m in rows]


@router.put("/{workspace_id}/members/{user_id}", response_model=WorkspaceMemberRead)
async def put_member(
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: WorkspaceMemberUpsert,
    session: SessionDep,
    access: WorkspaceOwner,
) -> WorkspaceMemberRead:
    member = await WorkspaceService(session).set_member(
        workspace_id, user_id, WorkspaceRole(payload.role)
    )
    await _audit(
        session,
        access.user.id,
        "WORKSPACE_MEMBER_SET",
        workspace_id,
        target=user_id,
        role=payload.role,
    )
    return WorkspaceMemberRead.model_validate(member)


@router.delete("/{workspace_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_member(
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    session: SessionDep,
    access: WorkspaceOwner,
) -> None:
    await WorkspaceService(session).remove_member(workspace_id, user_id)
    await _audit(session, access.user.id, "WORKSPACE_MEMBER_REMOVE", workspace_id, target=user_id)


# ── File Explorer ──────────────────────────────────────────────────────────
@router.get("/{workspace_id}/tree", response_model=FileNode)
async def get_tree(
    workspace_id: uuid.UUID,
    session: SessionDep,
    _access: WorkspaceViewer,
    path: str = Query(default=""),
    depth: int | None = Query(default=None, ge=1, le=64),
) -> FileNode:
    svc = WorkspaceService(session)
    await svc.get(workspace_id)
    tree = await _fs(svc, workspace_id).list_tree(rel_path=path, depth=depth)
    return FileNode.model_validate(tree, from_attributes=True)


@router.get("/{workspace_id}/file", response_model=FileContentRead)
async def read_file(
    workspace_id: uuid.UUID,
    session: SessionDep,
    _access: WorkspaceViewer,
    path: str = Query(min_length=1),
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
    access: WorkspaceEditor,
    path: str = Query(min_length=1),
    if_match: str | None = Header(default=None, alias="If-Match"),
) -> FileContentRead:
    svc = WorkspaceService(session)
    await svc.get_active(workspace_id)
    content = await _fs(svc, workspace_id).write_file(
        path, text=payload.text, notebook=payload.notebook, if_match=if_match
    )
    await _audit(session, access.user.id, "WORKSPACE_FS_WRITE", workspace_id, path=path)
    _log_op("SAVE", workspace_id=workspace_id, user_id=access.user.id, path=path)
    return FileContentRead.model_validate(content, from_attributes=True)


_READ_EXAMPLE = {
    ".csv": 'pd.read_csv("{p}")',
    ".tsv": 'pd.read_csv("{p}", sep="\\t")',
    ".parquet": 'pd.read_parquet("{p}")',
    ".json": 'pd.read_json("{p}")',
    ".xlsx": 'pd.read_excel("{p}")',
    ".txt": 'open("{p}").read()',
}


@router.get("/{workspace_id}/file/paths", response_model=FilePathsRead)
async def file_paths(
    workspace_id: uuid.UUID,
    session: SessionDep,
    _access: WorkspaceViewer,
    path: str = Query(min_length=1),
    from_path: str | None = Query(default=None),
) -> FilePathsRead:
    """Caminhos canônicos de um arquivo (para Copy Path / Copy Read Example).

    `from_path` (opcional): caminho de um notebook aberto — usado para o
    `read_example` com caminho relativo.
    """
    import contextlib
    from posixpath import basename, dirname, relpath

    svc = WorkspaceService(session)
    workspace = await svc.get(workspace_id)
    content = await _fs(svc, workspace_id).read_file(path)  # 404 se não existir
    rel = content.path
    ext = ("." + rel.rsplit(".", 1)[-1].lower()) if "." in rel else ""
    example_target = rel
    if from_path:
        with contextlib.suppress(ValueError):
            example_target = relpath(rel, dirname(from_path))
    tmpl = _READ_EXAMPLE.get(ext)
    read_example = tmpl.format(p=example_target) if tmpl else None
    # `workspace.name` é texto livre — barras quebrariam o caminho lógico.
    display_name = workspace.name.replace("/", "-").strip() or workspace.slug
    return FilePathsRead(
        path=rel,
        name=basename(rel),
        parent_path=dirname(rel),
        workspace_path=f"/{display_name}/{rel}",
        repository_path=rel,  # relativo ao repo git (== path enquanto não há remoto)
        read_example=read_example,
    )


@router.get("/{workspace_id}/data", response_model=DataPreviewRead)
async def read_data(
    workspace_id: uuid.UUID,
    session: SessionDep,
    _access: WorkspaceViewer,
    path: str = Query(min_length=1),
    offset: int = Query(default=0, ge=0),
    limit: int | None = Query(default=None, ge=1),
) -> DataPreviewRead:
    svc = WorkspaceService(session)
    await svc.get(workspace_id)
    settings = get_settings()
    capped = min(limit or 100, settings.workspace_data_max_rows)
    preview = await _fs(svc, workspace_id).read_data(path, offset=offset, limit=capped)
    return DataPreviewRead.model_validate(preview, from_attributes=True)


@router.get("/{workspace_id}/export")
async def export_notebook(
    workspace_id: uuid.UUID,
    session: SessionDep,
    _access: WorkspaceViewer,
    path: str = Query(min_length=1),
    fmt: str = Query(default="ipynb", pattern="^(ipynb|py)$"),
) -> Response:
    svc = WorkspaceService(session)
    await svc.get(workspace_id)
    data, filename, media_type = await _fs(svc, workspace_id).export_notebook(path, fmt)
    return Response(
        content=data,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{workspace_id}/dir", response_model=FileNode, status_code=status.HTTP_201_CREATED)
async def make_dir(
    workspace_id: uuid.UUID,
    session: SessionDep,
    access: WorkspaceEditor,
    path: str = Query(min_length=1),
) -> FileNode:
    svc = WorkspaceService(session)
    await svc.get_active(workspace_id)
    node = await _fs(svc, workspace_id).make_dir(path)
    await _audit(session, access.user.id, "WORKSPACE_FS_MKDIR", workspace_id, path=path)
    _log_op("CREATE_FOLDER", workspace_id=workspace_id, user_id=access.user.id, path=path)
    return FileNode.model_validate(node, from_attributes=True)


@router.delete("/{workspace_id}/file", status_code=status.HTTP_204_NO_CONTENT)
async def delete_entry(
    workspace_id: uuid.UUID,
    session: SessionDep,
    access: WorkspaceEditor,
    path: str = Query(min_length=1),
    recursive: bool = Query(default=False),
) -> None:
    svc = WorkspaceService(session)
    await svc.get_active(workspace_id)
    await _fs(svc, workspace_id).delete(path, recursive=recursive)
    await _audit(session, access.user.id, "WORKSPACE_FS_DELETE", workspace_id, path=path)
    _log_op("DELETE", workspace_id=workspace_id, user_id=access.user.id, path=path)


@router.post("/{workspace_id}/rename", response_model=FileNode)
async def rename_entry(
    workspace_id: uuid.UUID,
    payload: RenameRequest,
    session: SessionDep,
    access: WorkspaceEditor,
) -> FileNode:
    svc = WorkspaceService(session)
    await svc.get_active(workspace_id)
    node = await _fs(svc, workspace_id).rename(payload.src, payload.dst)
    await _audit(
        session,
        access.user.id,
        "WORKSPACE_FS_RENAME",
        workspace_id,
        src=payload.src,
        dst=payload.dst,
    )
    _log_op(
        "RENAME",
        workspace_id=workspace_id,
        user_id=access.user.id,
        old_path=payload.src,
        new_path=payload.dst,
    )
    return FileNode.model_validate(node, from_attributes=True)


@router.post("/{workspace_id}/copy", response_model=FileNode)
async def copy_entry(
    workspace_id: uuid.UUID,
    payload: CopyRequest,
    session: SessionDep,
    access: WorkspaceEditor,
) -> FileNode:
    svc = WorkspaceService(session)
    await svc.get_active(workspace_id)
    node = await _fs(svc, workspace_id).copy(payload.src, payload.dst)
    await _audit(
        session,
        access.user.id,
        "WORKSPACE_FS_COPY",
        workspace_id,
        src=payload.src,
        dst=payload.dst,
    )
    _log_op(
        "DUPLICATE",
        workspace_id=workspace_id,
        user_id=access.user.id,
        src=payload.src,
        dst=payload.dst,
    )
    return FileNode.model_validate(node, from_attributes=True)


@router.post("/{workspace_id}/upload", response_model=FileNode, status_code=status.HTTP_201_CREATED)
async def upload_file(
    workspace_id: uuid.UUID,
    session: SessionDep,
    access: WorkspaceEditor,
    file: UploadFile = File(...),
    path: str = Query(default=""),
) -> FileNode:
    svc = WorkspaceService(session)
    await svc.get_active(workspace_id)
    node = await _fs(svc, workspace_id).save_upload(path, file.filename or "arquivo", file)
    await _audit(session, access.user.id, "WORKSPACE_FS_UPLOAD", workspace_id, path=node.path)
    _log_op("UPLOAD", workspace_id=workspace_id, user_id=access.user.id, path=node.path)
    return FileNode.model_validate(node, from_attributes=True)


@router.post(
    "/{workspace_id}/generate",
    response_model=FileNode,
    status_code=status.HTTP_201_CREATED,
)
async def generate_file(
    workspace_id: uuid.UUID,
    payload: GenerateFileRequest,
    session: SessionDep,
    access: WorkspaceEditor,
) -> FileNode:
    """Gera um arquivo sintético grande (ex.: CSV de 1.000.000 de linhas).

    A geração roda em thread, streaming direto para disco — não passa pelo
    navegador nem carrega o arquivo em memória.
    """
    svc = WorkspaceService(session)
    await svc.get_active(workspace_id)
    node = await _fs(svc, workspace_id).generate_csv(
        payload.path, rows=payload.rows, seed=payload.seed
    )
    await _audit(
        session,
        access.user.id,
        "WORKSPACE_FS_GENERATE",
        workspace_id,
        path=payload.path,
        rows=payload.rows,
    )
    _log_op(
        "GENERATE",
        workspace_id=workspace_id,
        user_id=access.user.id,
        path=payload.path,
        rows=str(payload.rows),
    )
    return FileNode.model_validate(node, from_attributes=True)


@router.post(
    "/{workspace_id}/execute",
    response_model=ExecutionRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def execute_workspace_notebook(
    workspace_id: uuid.UUID,
    payload: WorkspaceExecuteRequest,
    session: SessionDep,
    redis: RedisDep,
    access: WorkspaceEditor,
) -> ExecutionRead:
    """Executa um `.ipynb` do Workspace via Papermill (source=WORKSPACE).

    Execução de *produção* — não confundir com o kernel interativo (Fase 4).
    """
    if not is_ipynb(payload.notebook_path):
        raise DomainValidationError("Só é possível executar arquivos .ipynb.")
    svc = WorkspaceService(session)
    await svc.get_active(workspace_id)
    # valida que o arquivo existe e está dentro do Workspace
    await _fs(svc, workspace_id).read_file(payload.notebook_path)

    exec_service = ExecutionService(session)
    execution, created = await exec_service.create_for_workspace(
        workspace_id,
        payload.notebook_path,
        parameters=payload.parameters,
        idempotency_key=payload.idempotency_key,
    )
    result = ExecutionRead.model_validate(execution)
    if created:
        await _audit(
            session,
            access.user.id,
            "EXECUTE_WORKSPACE_NOTEBOOK",
            workspace_id,
            path=payload.notebook_path,
        )
        await session.commit()
        await ExecutionQueue(redis).enqueue(str(execution.id), attempt=1)
    return result


@router.get("/{workspace_id}/download")
async def download(
    workspace_id: uuid.UUID,
    session: SessionDep,
    _access: WorkspaceViewer,
    path: str = Query(min_length=1),
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
