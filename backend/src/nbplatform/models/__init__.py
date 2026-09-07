"""Modelos SQLAlchemy. Importa todos os agregados para o metadata do Alembic."""

from nbplatform.db.base import Base
from nbplatform.models.audit import AuditLog
from nbplatform.models.config_vars import Secret, Variable
from nbplatform.models.execution import Execution, ExecutionLog
from nbplatform.models.job import Job, JobLog, JobTask
from nbplatform.models.notebook import Notebook, NotebookVersion
from nbplatform.models.notification import (
    Notification,
    NotificationConfig,
    NotificationSettings,
)
from nbplatform.models.schedule import Schedule
from nbplatform.models.user import User
from nbplatform.models.workflow import Workflow, WorkflowDependency, WorkflowTask

__all__ = [
    "Base",
    "AuditLog",
    "Secret",
    "Variable",
    "Execution",
    "ExecutionLog",
    "Job",
    "JobLog",
    "JobTask",
    "Notebook",
    "NotebookVersion",
    "Notification",
    "NotificationConfig",
    "NotificationSettings",
    "Schedule",
    "User",
    "Workflow",
    "WorkflowDependency",
    "WorkflowTask",
]
