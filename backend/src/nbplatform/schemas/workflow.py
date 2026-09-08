from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from nbplatform.domain.enums import TaskType, WorkflowStatus


class WorkflowCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10_000)


class WorkflowUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10_000)
    status: WorkflowStatus | None = None


class WorkflowRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    status: WorkflowStatus
    created_at: datetime
    updated_at: datetime


# ── grafo ────────────────────────────────────────────────────────────────────


class WorkflowTaskInput(BaseModel):
    # `key` estável vindo do cliente: id da task existente (UUID str) ou id temporário.
    key: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    type: TaskType = TaskType.NOTEBOOK
    notebook_id: uuid.UUID | None = None  # legado
    workspace_id: uuid.UUID | None = None
    notebook_path: str | None = Field(default=None, max_length=1024)
    parameters: dict[str, Any] = Field(default_factory=dict)
    timeout_s: int | None = Field(default=None, ge=1)
    max_retries: int = Field(default=0, ge=0, le=20)
    retry_policy: dict[str, Any] = Field(default_factory=dict)
    ui_position: dict[str, float] | None = None


class WorkflowEdgeInput(BaseModel):
    from_key: str
    to_key: str


class WorkflowGraphSave(BaseModel):
    tasks: list[WorkflowTaskInput] = Field(default_factory=list)
    dependencies: list[WorkflowEdgeInput] = Field(default_factory=list)


class WorkflowTaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    type: TaskType
    notebook_id: uuid.UUID | None
    workspace_id: uuid.UUID | None = None
    notebook_path: str | None = None
    parameters: dict[str, Any]
    timeout_s: int | None
    max_retries: int
    retry_policy: dict[str, Any]
    ui_position: dict[str, float] | None


class WorkflowDependencyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    from_task_id: uuid.UUID
    to_task_id: uuid.UUID


class WorkflowDetail(WorkflowRead):
    tasks: list[WorkflowTaskRead] = Field(default_factory=list)
    dependencies: list[WorkflowDependencyRead] = Field(default_factory=list)
