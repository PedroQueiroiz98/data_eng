from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from nbplatform.domain.assistant import AssistantProviderType, AssistantTask

MASK = "********"
MAX_CELLS = 500


# ─── providers ──────────────────────────────────────────────────────────────
class AssistantProviderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    provider_type: AssistantProviderType
    enabled: bool
    is_default: bool
    configuration: dict[str, Any]  # = configuration_json, sem a API key
    has_key: bool
    summary: str
    created_at: datetime
    updated_at: datetime


class AssistantProviderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    provider_type: AssistantProviderType
    enabled: bool = False
    is_default: bool = False
    configuration: dict[str, Any] = Field(default_factory=dict)
    secret: str | None = None  # write-only: API key


class AssistantProviderUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    enabled: bool | None = None
    is_default: bool | None = None
    configuration: dict[str, Any] | None = None
    secret: str | None = None  # None / "" / MASK mantém


class AssistantProviderEnabledPatch(BaseModel):
    enabled: bool


class AssistantTestResult(BaseModel):
    ok: bool
    detail: str = ""
    error: str | None = None


# ─── contexto / execução ───────────────────────────────────────────────────
class ErrorIn(BaseModel):
    ename: str = ""
    evalue: str = ""
    traceback: list[str] = Field(default_factory=list)


class AssistantContextIn(BaseModel):
    cells: list[str] = Field(min_length=1, max_length=MAX_CELLS)
    active_cell_index: int = Field(ge=0)
    cursor_line: int | None = Field(default=None, ge=0)
    cursor_column: int | None = Field(default=None, ge=0)
    selection: str | None = None
    recent_error: ErrorIn | None = None
    notebook_path: str | None = Field(default=None, max_length=1024)
    session_id: str | None = Field(default=None, max_length=40)
    workspace_files: list[str] | None = None


class ChatMessageIn(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class AssistantRunRequest(BaseModel):
    task: AssistantTask
    context: AssistantContextIn
    instruction: str | None = Field(default=None, max_length=8000)
    messages: list[ChatMessageIn] | None = None
    target_language: str | None = Field(default=None, max_length=40)
    cell_id: str | None = Field(default=None, max_length=64)


class AssistantRunResponse(BaseModel):
    ok: bool
    text: str = ""
    model: str = ""
    finish_reason: str = ""
    usage: dict[str, int] = Field(default_factory=dict)
    error: str | None = None
    interaction_id: str | None = None


class InlineCompleteRequest(BaseModel):
    context: AssistantContextIn


class InlineCompleteResponse(BaseModel):
    ok: bool
    completion: str = ""


class AssistantAvailability(BaseModel):
    configured: bool
    provider_type: str | None = None
    inline_enabled: bool = False
    models: list[str] = Field(default_factory=list)


class AssistantInteractionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    task: AssistantTask
    provider_type: AssistantProviderType | None
    notebook_path: str | None
    cell_id: str | None
    model: str | None
    prompt_chars: int
    completion_chars: int
    duration_ms: int | None
    ok: bool
    error: str | None
    result_text: str | None
    title: str | None
    created_at: datetime


class AssistantInteractionPage(BaseModel):
    items: list[AssistantInteractionRead]
    total: int
    limit: int
    offset: int
