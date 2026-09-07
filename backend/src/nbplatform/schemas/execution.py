from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from nbplatform.domain.enums import ExecutionStatus, LogLevel


class ExecutionCreate(BaseModel):
    parameters: dict[str, Any] = Field(default_factory=dict)
    # Versão específica; se omitida, usa a versão atual do notebook.
    notebook_version_number: int | None = None
    idempotency_key: str | None = Field(default=None, max_length=200)


class ExecutionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    notebook_version_id: uuid.UUID
    status: ExecutionStatus
    attempt: int
    parameters: dict[str, Any]
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    duration_ms: int | None
    error_code: str | None
    error_message: str | None
    worker_id: str | None


class ExecutionDetail(ExecutionRead):
    output_notebook_path: str | None = None
    has_output: bool = False


class ExecutionLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    seq: int
    ts: datetime
    level: LogLevel
    message: str
    attempt: int
