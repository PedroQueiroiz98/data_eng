"""Schemas do kernel interativo."""

from __future__ import annotations

from pydantic import BaseModel, Field


class KernelSessionCreate(BaseModel):
    notebook_path: str = Field(min_length=1, max_length=1024)


class KernelSessionRead(BaseModel):
    session_id: str
    status: str
    execution_count: int = 0
    notebook_path: str


class KernelExecuteRequest(BaseModel):
    cell_id: str = Field(min_length=1, max_length=128)
    code: str = Field(max_length=1_000_000)


class KernelExecuteAccepted(BaseModel):
    request_id: str
