"""Enums do domínio. Fonte única da verdade para status e classificações.

Usados por modelos SQLAlchemy, schemas Pydantic e serviços.
"""

from __future__ import annotations

from enum import StrEnum


class ExecutionStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    TIMEOUT = "TIMEOUT"


class JobStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class JobTaskStatus(StrEnum):
    PENDING = "PENDING"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    SKIPPED = "SKIPPED"


class WorkflowStatus(StrEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"
    ARCHIVED = "ARCHIVED"
    # Uma etapa aponta para um notebook que não existe mais no Workspace.
    INVALID = "INVALID"


class TaskType(StrEnum):
    NOTEBOOK = "NOTEBOOK"
    PYTHON = "PYTHON"


class TriggerType(StrEnum):
    MANUAL = "MANUAL"
    SCHEDULED = "SCHEDULED"
    API = "API"


class LogLevel(StrEnum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class ErrorClass(StrEnum):
    TRANSIENT = "TRANSIENT"
    PERMANENT = "PERMANENT"
    UNKNOWN = "UNKNOWN"


class RetryMode(StrEnum):
    ANY = "ANY"
    TRANSIENT_ONLY = "TRANSIENT_ONLY"


class ExecutionSource(StrEnum):
    """De onde vem o notebook de uma Execution.

    DB        → `executions.notebook_version_id` (fluxo legado, notebook no Postgres).
    WORKSPACE → `executions.workspace_id` + `executions.notebook_path` (arquivo em disco).
    """

    DB = "DB"
    WORKSPACE = "WORKSPACE"


class GitProvider(StrEnum):
    GITHUB = "GITHUB"
    GITLAB = "GITLAB"
    BITBUCKET = "BITBUCKET"
    AZURE_DEVOPS = "AZURE_DEVOPS"


class WorkspaceRole(StrEnum):
    """Papel de um usuário num Workspace (ACL). Ordem: VIEWER < EDITOR < OWNER.

    VIEWER → lê árvore/arquivos, baixa.
    EDITOR → + escreve/cria/renomeia/remove/upload, executa.
    OWNER  → + gerencia membros, edita/exclui o Workspace, conecta Git.
    """

    VIEWER = "VIEWER"
    EDITOR = "EDITOR"
    OWNER = "OWNER"


WORKSPACE_ROLE_RANK: dict[WorkspaceRole, int] = {
    WorkspaceRole.VIEWER: 1,
    WorkspaceRole.EDITOR: 2,
    WorkspaceRole.OWNER: 3,
}
