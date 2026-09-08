"""Modelos SQLAlchemy. Importa todos os agregados para o metadata do Alembic."""

from nbplatform.db.base import Base
from nbplatform.models.audit import AuditLog
from nbplatform.models.config_vars import Secret, Variable
from nbplatform.models.execution import Execution, ExecutionLog
from nbplatform.models.job import Job, JobLog, JobTask
from nbplatform.models.notebook import Notebook, NotebookVersion
from nbplatform.models.notification import (
    NotificationDelivery,
    NotificationProvider,
)
from nbplatform.models.schedule import Schedule
from nbplatform.models.user import User
from nbplatform.models.workflow import Workflow, WorkflowDependency, WorkflowTask
from nbplatform.models.workspace import (
    Workspace,
    WorkspaceGitRepository,
    WorkspaceMember,
)

__all__ = [
    "Base",
    "AuditLog",
    "Workspace",
    "WorkspaceGitRepository",
    "WorkspaceMember",
    "Secret",
    "Variable",
    "Execution",
    "ExecutionLog",
    "Job",
    "JobLog",
    "JobTask",
    "Notebook",
    "NotebookVersion",
    "NotificationDelivery",
    "NotificationProvider",
    "Schedule",
    "User",
    "Workflow",
    "WorkflowDependency",
    "WorkflowTask",
]
