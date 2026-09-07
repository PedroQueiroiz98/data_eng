from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ScheduleCreate(BaseModel):
    workflow_id: uuid.UUID
    cron: str = Field(min_length=1, max_length=120)
    timezone: str = Field(default="UTC", max_length=64)
    enabled: bool = True
    parameters: dict[str, Any] = Field(default_factory=dict)


class ScheduleUpdate(BaseModel):
    cron: str | None = Field(default=None, min_length=1, max_length=120)
    timezone: str | None = Field(default=None, max_length=64)
    enabled: bool | None = None
    parameters: dict[str, Any] | None = None


class ScheduleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workflow_id: uuid.UUID
    cron: str
    timezone: str
    enabled: bool
    parameters: dict[str, Any]
    last_run_at: datetime | None
    next_run_at: datetime | None
    created_at: datetime
