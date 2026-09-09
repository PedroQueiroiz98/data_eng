"""Endpoints do Workspace **único** (`/root`): File Explorer + execução.

Modo single-workspace: não há CRUD de Workspace nem ACL de membros. Qualquer
usuário autenticado é EDITOR do Workspace `/root` (admin global é OWNER).
Todas as rotas operam sobre `settings.workspace_dir` (mostrado como `/root`).
"""

from __future__ import annotations

import contextlib
import io
import logging
import uuid
from collections.abc import Iterator
from pathlib import Path
from posixpath import basename, dirname, relpath

from fastapi import APIRouter, File, Header, Query, UploadFile, status
from fastapi.responses import Response, StreamingResponse

from nbplatform.api.deps import (
    RedisDep,
    SessionDep,
    WorkspaceEditor,
    WorkspaceViewer,
)
from nbplatform.core.config import get_settings
from nbplatform.core.errors import DomainValidationError
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
    WorkspaceDetail,
    WorkspaceExecuteRequest,
    WriteFileRequest,
)
from nbplatform.services.audit_service import AuditService
from nbplatform.services.execution_service import ExecutionService
from nbplatform.services.workflow_service import WorkflowService
from nbplatform.services.workspace_fs_service import WorkspaceFsService
from nbplatform.services.workspace_service import SINGLETON_WORKSPACE_ID, WorkspaceService

router = APIRouter(prefix="/api/workspace", tags=["workspace"])
logger = logging.getLogger("nbplatform.workspace.fs")

_WID = SINGLETON_WORKSPACE_ID


def _log_op(
    operation: str,
    *,
    user_id: uuid.UUID,
    status_: str = "SUCCESS",
    **paths: str | None,
) -> None:
    """Log estruturado de operação de arquivo do Workspace."""
    logger.info(
        "workspace file operation",
        extra={
            "operation": operation,
            "workspace_id": str(_WID),
            "user_id": str(user_id),
            "status": status_,
            **{k: v for k, v in paths.items() if v is not None},
        },
    )


def _fs() -> WorkspaceFsService:
    settings = get_settings()
    return WorkspaceFsService(
        Path(settings.workspace_dir),
        max_upload_bytes=settings.workspace_max_upload_bytes,
        max_nodes=settings.workspace_tree_max_nodes,
        max_depth=settings.workspace_tree_max_depth,
    )


async def _audit(
    session: SessionDep, user_id: uuid.UUID, action: str, **meta: object
) -> None:
    await AuditService(session).record(
        user_id=user_id,
        action=action,
        resource_type="workspace",
        resource_id=str(_WID),
        metadata={k: str(v) for k, v in meta.items()} or None,
    )


# ── Workspace (metadados do singleton) ─────────────────────────────────────
@router.get("", response_model=WorkspaceDetail)
async def get_workspace(session: SessionDep, _access: WorkspaceViewer) -> WorkspaceDetail:
    workspace = await WorkspaceService(session).get_singleton()
    return WorkspaceDetail.model_validate(workspace)


# ── File Explorer ──────────────────────────────────────────────────────────
@router.get("/tree", response_model=FileNode)
async def get_tree(
    _access: WorkspaceViewer,
    path: str = Query(default=""),
    depth: int | None = Query(default=None, ge=1, le=64),
) -> FileNode:
    tree = await _fs().list_tree(rel_path=path, depth=depth)
    return FileNode.model_validate(tree, from_attributes=True)


@router.get("/file", response_model=FileContentRead)
async def read_file(
    _access: WorkspaceViewer,
    path: str = Query(min_length=1),
) -> FileContentRead:
    content = await _fs().read_file(path)
    return FileContentRead.model_validate(content, from_attributes=True)


@router.put("/file", response_model=FileContentRead)
async def write_file(
    payload: WriteFileRequest,
    session: SessionDep,
    access: WorkspaceEditor,
    path: str = Query(min_length=1),
    if_match: str | None = Header(default=None, alias="If-Match"),
) -> FileContentRead:
    content = await _fs().write_file(
        path, text=payload.text, notebook=payload.notebook, if_match=if_match
    )
    await _audit(session, access.user.id, "WORKSPACE_FS_WRITE", path=path)
    _log_op("SAVE", user_id=access.user.id, path=path)
    return FileContentRead.model_validate(content, from_attributes=True)


_READ_EXAMPLE = {
    ".csv": 'pd.read_csv("{p}")',
    ".tsv": 'pd.read_csv("{p}", sep="\\t")',
    ".parquet": 'pd.read_parquet("{p}")',
    ".json": 'pd.read_json("{p}")',
    ".xlsx": 'pd.read_excel("{p}")',
    ".txt": 'open("{p}").read()',
}


@router.get("/file/paths", response_model=FilePathsRead)
async def file_paths(
    _access: WorkspaceViewer,
    path: str = Query(min_length=1),
    from_path: str | None = Query(default=None),
) -> FilePathsRead:
    """Caminhos canônicos de um arquivo (para Copy Path / Copy Read Example)."""
    content = await _fs().read_file(path)  # 404 se não existir
    rel = content.path
    ext = ("." + rel.rsplit(".", 1)[-1].lower()) if "." in rel else ""
    example_target = rel
    if from_path:
        with contextlib.suppress(ValueError):
            example_target = relpath(rel, dirname(from_path))
    tmpl = _READ_EXAMPLE.get(ext)
    read_example = tmpl.format(p=example_target) if tmpl else None
    return FilePathsRead(
        path=rel,
        name=basename(rel),
        parent_path=dirname(rel),
        workspace_path=f"/root/{rel}",
        repository_path=rel,
        read_example=read_example,
    )


@router.get("/data", response_model=DataPreviewRead)
async def read_data(
    _access: WorkspaceViewer,
    path: str = Query(min_length=1),
    offset: int = Query(default=0, ge=0),
    limit: int | None = Query(default=None, ge=1),
) -> DataPreviewRead:
    settings = get_settings()
    capped = min(limit or 100, settings.workspace_data_max_rows)
    preview = await _fs().read_data(path, offset=offset, limit=capped)
    return DataPreviewRead.model_validate(preview, from_attributes=True)


@router.get("/export")
async def export_notebook(
    _access: WorkspaceViewer,
    path: str = Query(min_length=1),
    fmt: str = Query(default="ipynb", pattern="^(ipynb|py)$"),
) -> Response:
    data, filename, media_type = await _fs().export_notebook(path, fmt)
    return Response(
        content=data,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/dir", response_model=FileNode, status_code=status.HTTP_201_CREATED)
async def make_dir(
    session: SessionDep,
    access: WorkspaceEditor,
    path: str = Query(min_length=1),
) -> FileNode:
    node = await _fs().make_dir(path)
    await _audit(session, access.user.id, "WORKSPACE_FS_MKDIR", path=path)
    _log_op("CREATE_FOLDER", user_id=access.user.id, path=path)
    return FileNode.model_validate(node, from_attributes=True)


@router.delete("/file", status_code=status.HTTP_204_NO_CONTENT)
async def delete_entry(
    session: SessionDep,
    access: WorkspaceEditor,
    path: str = Query(min_length=1),
    recursive: bool = Query(default=False),
) -> None:
    await _fs().delete(path, recursive=recursive)
    # Workflows que referenciam este notebook (ou algo sob esta pasta) ficam
    # inválidos — o usuário decide localizar/remover a etapa.
    await WorkflowService(session).invalidate_referencing(path)
    await _audit(session, access.user.id, "WORKSPACE_FS_DELETE", path=path)
    _log_op("DELETE", user_id=access.user.id, path=path)


@router.post("/rename", response_model=FileNode)
async def rename_entry(
    payload: RenameRequest,
    session: SessionDep,
    access: WorkspaceEditor,
) -> FileNode:
    node = await _fs().rename(payload.src, payload.dst)
    # Referências de Workflow acompanham o rename/move (ID estável via path fixup).
    repathed = await WorkflowService(session).repath_tasks(payload.src, payload.dst)
    await _audit(
        session, access.user.id, "WORKSPACE_FS_RENAME", src=payload.src, dst=payload.dst
    )
    _log_op(
        "RENAME",
        user_id=access.user.id,
        old_path=payload.src,
        new_path=payload.dst,
        workflow_tasks_repathed=str(repathed),
    )
    return FileNode.model_validate(node, from_attributes=True)


@router.post("/copy", response_model=FileNode)
async def copy_entry(
    payload: CopyRequest,
    session: SessionDep,
    access: WorkspaceEditor,
) -> FileNode:
    node = await _fs().copy(payload.src, payload.dst)
    await _audit(
        session, access.user.id, "WORKSPACE_FS_COPY", src=payload.src, dst=payload.dst
    )
    _log_op("DUPLICATE", user_id=access.user.id, src=payload.src, dst=payload.dst)
    return FileNode.model_validate(node, from_attributes=True)


@router.post("/upload", response_model=FileNode, status_code=status.HTTP_201_CREATED)
async def upload_file(
    session: SessionDep,
    access: WorkspaceEditor,
    file: UploadFile = File(...),
    path: str = Query(default=""),
) -> FileNode:
    node = await _fs().save_upload(path, file.filename or "arquivo", file)
    await _audit(session, access.user.id, "WORKSPACE_FS_UPLOAD", path=node.path)
    _log_op("UPLOAD", user_id=access.user.id, path=node.path)
    return FileNode.model_validate(node, from_attributes=True)


@router.post("/generate", response_model=FileNode, status_code=status.HTTP_201_CREATED)
async def generate_file(
    payload: GenerateFileRequest,
    session: SessionDep,
    access: WorkspaceEditor,
) -> FileNode:
    """Gera um arquivo sintético grande (ex.: CSV de 1.000.000 de linhas)."""
    node = await _fs().generate_csv(payload.path, rows=payload.rows, seed=payload.seed)
    await _audit(
        session, access.user.id, "WORKSPACE_FS_GENERATE", path=payload.path, rows=payload.rows
    )
    _log_op("GENERATE", user_id=access.user.id, path=payload.path, rows=str(payload.rows))
    return FileNode.model_validate(node, from_attributes=True)


@router.post("/execute", response_model=ExecutionRead, status_code=status.HTTP_202_ACCEPTED)
async def execute_workspace_notebook(
    payload: WorkspaceExecuteRequest,
    session: SessionDep,
    redis: RedisDep,
    access: WorkspaceEditor,
) -> ExecutionRead:
    """Executa um `.ipynb` do Workspace via Papermill (source=WORKSPACE)."""
    if not is_ipynb(payload.notebook_path):
        raise DomainValidationError("Só é possível executar arquivos .ipynb.")
    await _fs().read_file(payload.notebook_path)  # 404 se não existir

    exec_service = ExecutionService(session)
    execution, created = await exec_service.create_for_workspace(
        _WID,
        payload.notebook_path,
        parameters=payload.parameters,
        idempotency_key=payload.idempotency_key,
    )
    result = ExecutionRead.model_validate(execution)
    if created:
        await _audit(
            session, access.user.id, "EXECUTE_WORKSPACE_NOTEBOOK", path=payload.notebook_path
        )
        await session.commit()
        await ExecutionQueue(redis).enqueue(str(execution.id), attempt=1)
    return result


@router.get("/download")
async def download(
    _access: WorkspaceViewer,
    path: str = Query(min_length=1),
) -> Response:
    source, name, is_zip = await _fs().open_download(path)
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
