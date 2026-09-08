"""Schemas do Git local do Workspace."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class GitChangeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    path: str
    index: str
    worktree: str


class GitStatusRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    initialized: bool
    branch: str | None = None
    detached: bool = False
    ahead: int = 0
    behind: int = 0
    changes: list[GitChangeRead] = []


class GitCommitRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sha: str
    author: str
    date: str
    subject: str


class GitDiffRead(BaseModel):
    path: str | None = None
    diff: str


class GitBranchesRead(BaseModel):
    current: str | None = None
    branches: list[str] = []


class GitBranchCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class GitCheckoutRequest(BaseModel):
    ref: str = Field(min_length=1, max_length=200)


class GitCommitRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    paths: list[str] = Field(default_factory=list)


class GitDiscardRequest(BaseModel):
    paths: list[str] = Field(default_factory=list)


class GitCommitResult(BaseModel):
    sha: str
