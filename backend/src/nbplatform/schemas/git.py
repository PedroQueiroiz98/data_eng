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
    # merge em andamento (conflito de um `pull`/"Inicializar" anterior, ainda
    # não resolvido) e se há um remoto (`origin`) configurado.
    merging: bool = False
    remote_configured: bool = False


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


class GitRemoteLinkRequest(BaseModel):
    """"Inicializar Repositório no Workspace": vincula + faz o sync inicial."""

    repo_full_name: str = Field(min_length=1, max_length=300)  # "owner/repo"
    branch: str = Field(min_length=1, max_length=200)
    base_dir: str = Field(default="", max_length=500)


class GitPullRead(BaseModel):
    """Resultado de um `pull`/"Inicializar": lista de caminhos em conflito, se
    houver — um pull com conflitos não é um erro HTTP, é um estado válido que
    o usuário resolve editando os arquivos e comitando (ou abortando o merge)."""

    conflicts: list[str] = []


class GitPushResult(BaseModel):
    branch: str
