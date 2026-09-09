"""Schemas da integração GitHub (conta pessoal do usuário)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class GitHubConnectRequest(BaseModel):
    token: str = Field(min_length=1, max_length=500)


class GitHubAccountRead(BaseModel):
    connected: bool
    username: str | None = None
    email: str | None = None
    avatar_url: str | None = None
    repo_full_name: str | None = None
    repo_default_branch: str | None = None
    base_dir: str | None = None
    last_sync_at: datetime | None = None


class GitHubRepoRead(BaseModel):
    full_name: str
    private: bool
    default_branch: str
    clone_url: str
    updated_at: str


class GitHubBranchRead(BaseModel):
    name: str
