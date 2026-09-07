from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from nbplatform.domain.enums import JobStatus, JobTaskStatus, LogLevel, TriggerType


class JobRunRequest(BaseModel):
    parameters: dict[str, Any] = Field(default_factory=dict)


class JobTaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workflow_task_id: uuid.UUID
    execution_id: uuid.UUID | None
    status: JobTaskStatus
    attempt: int
    started_at: datetime | None
    finished_at: datetime | None
    duration_ms: int | None
    error_message: str | None
    name: str = ""  # preenchido a partir da workflow_task


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workflow_id: uuid.UUID
    status: JobStatus
    trigger_type: TriggerType
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    duration_ms: int | None


class JobDetail(JobRead):
    workflow_name: str = ""
    tasks: list[JobTaskRead] = Field(default_factory=list)
    dependencies: list[dict[str, str]] = Field(default_factory=list)


class JobLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    seq: int
    ts: datetime
    level: LogLevel
    message: str
    job_task_id: uuid.UUID | None
