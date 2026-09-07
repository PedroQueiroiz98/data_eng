from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class NotebookCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10_000)
    # Conteúdo .ipynb opcional; se omitido, cria um notebook vazio.
    content: dict[str, Any] | None = None


class NotebookUpdate(BaseModel):
    """Só metadados. Conteúdo muda via POST /versions (versões imutáveis)."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10_000)


class NotebookContentSave(BaseModel):
    content: dict[str, Any]


class NotebookVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    notebook_id: uuid.UUID
    version_number: int
    created_by: uuid.UUID | None
    created_at: datetime


class NotebookVersionDetail(NotebookVersionRead):
    content: dict[str, Any]


class NotebookRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    current_version: int
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class NotebookDetail(NotebookRead):
    """Metadados + conteúdo da versão atual (carga em 1 request para o editor)."""

    content: dict[str, Any] | None = None
    version_count: int = 0
