from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


# ── Workspace ────────────────────────────────────────────────────────────────
class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10_000)


class WorkspaceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10_000)
    is_active: bool | None = None


class WorkspaceGitSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    provider: str
    repo_url: str
    repo_owner: str | None
    repo_name: str | None
    default_branch: str | None
    current_branch: str | None
    last_sync_at: datetime | None


class WorkspaceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    description: str | None
    owner_id: uuid.UUID | None
    root_path: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class WorkspaceDetail(WorkspaceRead):
    git_repository: WorkspaceGitSummary | None = None


# ── Membros (ACL) ───────────────────────────────────────────────────────────
class WorkspaceMemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    role: Literal["VIEWER", "EDITOR", "OWNER"]
    created_at: datetime


class WorkspaceMemberUpsert(BaseModel):
    role: Literal["VIEWER", "EDITOR", "OWNER"]


# ── File Explorer ────────────────────────────────────────────────────────────
class FileNode(BaseModel):
    name: str
    path: str
    type: Literal["file", "dir"]
    size: int | None = None
    modified_at: float | None = None
    children: list[FileNode] | None = None


class FileContentRead(BaseModel):
    path: str
    kind: Literal["notebook", "text", "binary"]
    content: dict[str, Any] | str | None = None
    etag: str | None = None


class DataPreviewRead(BaseModel):
    columns: list[str]
    dtypes: list[str]
    rows: list[list[Any]]
    total: int | None = None
    truncated: bool = False
    offset: int = 0


class FilePathsRead(BaseModel):
    path: str  # relativo à raiz do Workspace
    name: str
    parent_path: str
    workspace_path: str  # "/<nome do workspace>/<rel>"
    repository_path: str  # rel ao repo git (== path por ora)
    read_example: str | None = None  # snippet pandas/open conforme extensão


class WriteFileRequest(BaseModel):
    # Exatamente um dos dois. `.ipynb` aceita `notebook` (dict) ou `text` (json).
    text: str | None = None
    notebook: dict[str, Any] | None = None


class RenameRequest(BaseModel):
    src: str = Field(min_length=1, alias="from")
    dst: str = Field(min_length=1, alias="to")

    model_config = ConfigDict(populate_by_name=True)


class CopyRequest(RenameRequest):
    pass


class BatchDeleteRequest(BaseModel):
    paths: list[str] = Field(min_length=1, max_length=500)
    recursive: bool = False


class BatchMoveItem(BaseModel):
    src: str = Field(min_length=1, alias="from")
    dst: str = Field(min_length=1, alias="to")

    model_config = ConfigDict(populate_by_name=True)


class BatchMoveRequest(BaseModel):
    items: list[BatchMoveItem] = Field(min_length=1, max_length=500)


class BatchItemResult(BaseModel):
    path: str
    ok: bool
    error: str | None = None
    new_path: str | None = None


class BatchResult(BaseModel):
    results: list[BatchItemResult]


class GenerateFileRequest(BaseModel):
    """Geração de arquivo sintético grande no backend (streaming em disco)."""

    path: str = Field(min_length=1, max_length=1024)
    kind: Literal["csv"] = "csv"
    rows: int = Field(ge=1, le=5_000_000)
    seed: int | None = None


# ── Execução de notebook do Workspace (Fase 2) ───────────────────────────────
class WorkspaceExecuteRequest(BaseModel):
    notebook_path: str = Field(min_length=1, max_length=1024)
    parameters: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = Field(default=None, max_length=200)
