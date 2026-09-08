"""Monta a `NotificationMessage` canônica a partir do contexto do Job."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nbplatform.core.config import get_settings
from nbplatform.domain.notifications import NotificationEventType, NotificationMessage
from nbplatform.models.execution import Execution
from nbplatform.models.job import Job, JobTask
from nbplatform.models.notebook import Notebook
from nbplatform.models.workflow import Workflow, WorkflowTask


async def build_workflow_message(
    session: AsyncSession, job: Job
) -> NotificationMessage:
    """Mensagem de nível run (WORKFLOW_FAILED): resumo do pipeline que falhou."""
    tasks = list(
        await session.scalars(select(JobTask).where(JobTask.job_id == job.id))
    )
    failed = next(
        (t for t in tasks if t.status.value in ("FAILED", "CANCELLED")), None
    )
    return await _build(
        session, job, failed, NotificationEventType.WORKFLOW_FAILED, "🚨 Pipeline falhou"
    )


async def build_job_message(
    session: AsyncSession, job: Job, job_task: JobTask
) -> NotificationMessage:
    """Mensagem de nível etapa (JOB_FAILED): a JobTask específica que falhou."""
    return await _build(
        session,
        job,
        job_task,
        NotificationEventType.JOB_FAILED,
        "🚨 Etapa do pipeline falhou",
    )


async def _build(
    session: AsyncSession,
    job: Job,
    failed: JobTask | None,
    event: NotificationEventType,
    title: str,
) -> NotificationMessage:
    settings = get_settings()
    wf = await session.get(Workflow, job.workflow_id)
    pipeline_name = wf.name if wf else str(job.workflow_id)

    ex: Execution | None = None
    wtask: WorkflowTask | None = None
    if failed is not None:
        wtask = await session.get(WorkflowTask, failed.workflow_task_id)
        if failed.execution_id:
            ex = await session.get(Execution, failed.execution_id)

    job_name = wtask.name if wtask else pipeline_name
    notebook_name: str | None = None
    if wtask and wtask.notebook_id:
        nb = await session.get(Notebook, wtask.notebook_id)
        notebook_name = nb.name if nb else None

    error_type: str | None = None
    error_message: str | None = None
    if ex and ex.error_message:
        error_message = ex.error_message
        error_type = (ex.error_code or "").strip() or _ename(ex.error_message)
    elif failed and failed.error_message:
        error_message = failed.error_message
        error_type = _ename(failed.error_message)

    execution_id = (
        str(failed.execution_id) if failed and failed.execution_id else str(job.id)
    )
    attempt = failed.attempt if failed and failed.attempt else 1
    duration_ms = job.duration_ms
    when = (job.finished_at or datetime.now(UTC)).isoformat()

    metadata: dict[str, str] = {
        "Ambiente": _environment(),
        "Erro": error_message or "—",
        "Componente": error_type or notebook_name or "—",
        "Evento": str(event),
        "Data/Hora": when,
        "Event ID": str(uuid.uuid4()),
        "Correlation ID": str(job.id),
        "Workflow": pipeline_name,
        "Job": job_name,
        "Execution ID": execution_id,
        "Attempt": str(attempt),
        "Duration": _fmt_duration(duration_ms),
    }

    return NotificationMessage(
        event_type=event,
        title=title,
        message=_body_text(pipeline_name, job_name, error_message),
        environment=_environment(),
        pipeline_name=pipeline_name,
        job_name=job_name,
        execution_id=execution_id,
        timestamp=job.finished_at or datetime.now(UTC),
        attempt=attempt,
        job_id=str(job.id),
        workflow_id=str(job.workflow_id),
        error_type=error_type,
        error_message=error_message,
        correlation_id=str(job.id),
        duration_ms=duration_ms,
        notebook_name=notebook_name,
        execution_url=f"{settings.app_base_url.rstrip('/')}/jobs/{job.id}",
        metadata=metadata,
    )


def _environment() -> str:
    env = get_settings().app_env
    return {"prod": "production", "dev": "development", "test": "test"}.get(env, env)


def _ename(message: str) -> str:
    head = message.split(":", 1)[0].strip()
    return head if head and " " not in head else ""


def _fmt_duration(ms: int | None) -> str:
    if ms is None:
        return "—"
    s = round(ms / 1000)
    return f"{s}s" if s < 60 else f"{s // 60}m {s % 60:02d}s"


def _body_text(pipeline: str, job_name: str, error: str | None) -> str:
    lines = [f"Workflow: {pipeline}", f"Job: {job_name}"]
    if error:
        lines += ["", "💥 Erro:", error]
    return "\n".join(lines)
