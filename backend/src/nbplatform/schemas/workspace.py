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


# ── Execução de notebook do Workspace (Fase 2) ───────────────────────────────
class WorkspaceExecuteRequest(BaseModel):
    notebook_path: str = Field(min_length=1, max_length=1024)
    parameters: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = Field(default=None, max_length=200)
