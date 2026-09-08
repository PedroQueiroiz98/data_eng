"""Orquestração de Jobs: cria JobTasks e avança o DAG conforme as Executions terminam."""

from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from redis.asyncio import Redis

from nbplatform.core.config import get_settings
from nbplatform.core.errors import NotFoundError
from nbplatform.db.session import session_scope
from nbplatform.domain.dag import validate_dag
from nbplatform.domain.enums import (
    ExecutionStatus,
    JobStatus,
    JobTaskStatus,
    LogLevel,
    TriggerType,
)
from nbplatform.domain.job_state import JOBTASK_BLOCKING_FAILURE, JOBTASK_TERMINAL
from nbplatform.domain.notifications import NotificationEvent, NotificationEventType
from nbplatform.models.job import Job, JobLog, JobTask
from nbplatform.queue.execution_queue import ExecutionQueue
from nbplatform.repositories.execution_repository import ExecutionRepository
from nbplatform.repositories.job_repository import JobRepository
from nbplatform.repositories.notebook_repository import NotebookRepository
from nbplatform.repositories.workflow_repository import WorkflowRepository
from nbplatform.services.execution_service import ExecutionService
from nbplatform.ws.events import make_event, publish_job_event

logger = logging.getLogger(__name__)

_EXEC_TERMINAL = {
    ExecutionStatus.SUCCESS,
    ExecutionStatus.FAILED,
    ExecutionStatus.TIMEOUT,
    ExecutionStatus.CANCELLED,
}


def _now() -> datetime:
    return datetime.now(UTC)


class JobOrchestrator:
    def __init__(self, redis: Redis) -> None:
        self.redis = redis
        self.settings = get_settings()
        self.queue = ExecutionQueue(redis)

    # ── criação ────────────────────────────────────────────────────────────
    async def start_job(
        self,
        workflow_id: uuid.UUID,
        *,
        trigger_type: TriggerType,
        created_by: uuid.UUID | None,
        parameters: dict[str, Any],
    ) -> uuid.UUID:
        to_enqueue: list[str] = []
        async with session_scope() as session:
            wf = await WorkflowRepository(session).get_with_graph(workflow_id)
            if wf is None:
                raise NotFoundError(f"Workflow {workflow_id} não encontrado.")

            wtask_by_id = {t.id: t for t in wf.tasks}
            edges = [(d.from_task_id, d.to_task_id) for d in wf.dependencies]
            validate_dag(set(wtask_by_id), edges)

            job = Job(
                workflow_id=workflow_id,
                status=JobStatus.RUNNING,
                trigger_type=trigger_type,
                created_by=created_by,
                parameters=parameters,
                started_at=_now(),
            )
            await JobRepository(session).add(job)

            job_tasks = {
                wtid: JobTask(job_id=job.id, workflow_task_id=wtid, status=JobTaskStatus.PENDING)
                for wtid in wtask_by_id
            }
            for jt in job_tasks.values():
                session.add(jt)
            await session.flush()

            await self._log(session, job.id, None, f"job iniciado ({len(job_tasks)} tarefas)")

            if not wtask_by_id:
                await self._finalize(session, job, JobStatus.SUCCESS)
                return job.id

            deps_of = _deps_of(edges)
            ready = [wtid for wtid in wtask_by_id if not deps_of[wtid]]
            for wtid in ready:
                exec_id = await self._launch_task(
                    session, job, job_tasks[wtid], wtask_by_id[wtid]
                )
                if exec_id:
                    to_enqueue.append(str(exec_id))

            job_id = job.id

        for eid in to_enqueue:
            await self.queue.enqueue(eid)
        await self._publish(job_id, make_event("status_changed", status=JobStatus.RUNNING))
        return job_id

    # ── avanço ─────────────────────────────────────────────────────────────
    async def sync_and_advance(self, job_id: uuid.UUID) -> JobStatus | None:
        to_enqueue: list[str] = []
        final_status: JobStatus | None = None
        async with session_scope() as session:
            repo = JobRepository(session)
            job = await repo.lock_if_running(job_id)
            if job is None:
                return None

            wf = await WorkflowRepository(session).get_with_graph(job.workflow_id)
            assert wf is not None
            wtask_by_id = {t.id: t for t in wf.tasks}
            edges = [(d.from_task_id, d.to_task_id) for d in wf.dependencies]
            deps_of = _deps_of(edges)

            tasks = await repo.tasks_for(job_id)
            jt_by_wtid = {t.workflow_task_id: t for t in tasks}
            exec_repo = ExecutionRepository(session)
            cancelling = await self._is_cancelling(job_id)

            # 1) sincroniza status das Executions -> JobTasks
            for jt in tasks:
                if jt.status not in (JobTaskStatus.QUEUED, JobTaskStatus.RUNNING):
                    continue
                if jt.execution_id is None:
                    continue
                ex = await exec_repo.get(jt.execution_id)
                if ex is None:
                    continue
                if ex.status == ExecutionStatus.RUNNING and jt.status == JobTaskStatus.QUEUED:
                    jt.status = JobTaskStatus.RUNNING
                    jt.started_at = ex.started_at
                elif ex.status in _EXEC_TERMINAL:
                    jt.status = _map_exec_status(ex.status)
                    jt.finished_at = ex.finished_at
                    jt.duration_ms = ex.duration_ms
                    jt.error_message = ex.error_message
                    jt.attempt = ex.attempt
                    name = wtask_by_id[jt.workflow_task_id].name
                    await self._log(
                        session, job_id, jt.id, f"tarefa '{name}' → {jt.status.value}"
                    )

            # 2) cancelamento: pendências viram CANCELLED, running recebe sinal
            if cancelling:
                _active = (JobTaskStatus.QUEUED, JobTaskStatus.RUNNING)
                for jt in tasks:
                    if jt.status == JobTaskStatus.PENDING:
                        jt.status = JobTaskStatus.CANCELLED
                        jt.finished_at = _now()
                    elif jt.status in _active and jt.execution_id:
                        await self.queue.request_cancel(str(jt.execution_id))

            # 3) avança: SKIPPED se dep falhou; lança se prontas
            completed = {
                w for w, jt in jt_by_wtid.items() if jt.status == JobTaskStatus.SUCCESS
            }
            blocked = {
                w
                for w, jt in jt_by_wtid.items()
                if jt.status in JOBTASK_BLOCKING_FAILURE
            }
            if not cancelling:
                progressed = True
                while progressed:
                    progressed = False
                    for wtid, jt in jt_by_wtid.items():
                        if jt.status != JobTaskStatus.PENDING:
                            continue
                        preds = deps_of[wtid]
                        if preds & blocked:
                            jt.status = JobTaskStatus.SKIPPED
                            jt.finished_at = _now()
                            blocked.add(wtid)
                            progressed = True
                            name = wtask_by_id[wtid].name
                            await self._log(
                                session, job_id, jt.id,
                                f"tarefa '{name}' → SKIPPED (dependência falhou)",
                            )
                        elif preds <= completed:
                            exec_id = await self._launch_task(
                                session, job, jt, wtask_by_id[wtid]
                            )
                            if exec_id:
                                to_enqueue.append(str(exec_id))

            # 4) finaliza?
            if all(jt.status in JOBTASK_TERMINAL for jt in tasks):
                if cancelling or any(
                    jt.status == JobTaskStatus.CANCELLED for jt in tasks
                ):
                    final_status = JobStatus.CANCELLED
                elif all(jt.status == JobTaskStatus.SUCCESS for jt in tasks):
                    final_status = JobStatus.SUCCESS
                else:
                    final_status = JobStatus.FAILED
                await self._finalize(session, job, final_status)

        for eid in to_enqueue:
            await self.queue.enqueue(eid)
        await self._publish(job_id, make_event("progress"))
        if final_status is not None:
            await self.queue.redis.delete(self.settings.job_cancel_key(str(job_id)))
            await self._publish(
                job_id, make_event("status_changed", status=final_status)
            )
            await self._notify_final(job_id, final_status)
        return final_status

    async def _notify_final(self, job_id: uuid.UUID, status: JobStatus) -> None:
        """Ponto central de notificação de falha (spec §20/§21).

        Emite WORKFLOW_FAILED (run) + JOB_FAILED por JobTask que falhou. Nunca
        levanta — o resultado do Job é independente das notificações.
        """
        if status != JobStatus.FAILED:
            return
        try:
            from nbplatform.services.notifications import NotificationService

            async with session_scope() as session:
                job = await session.get(Job, job_id)
                if job is None:
                    return
                workflow_id = job.workflow_id
                finished_at = job.finished_at or _now()
                tasks = await JobRepository(session).tasks_for(job_id)
                failed = [
                    (t.id, t.execution_id, t.finished_at)
                    for t in tasks
                    if t.status == JobTaskStatus.FAILED
                ]

            svc = NotificationService(self.redis)
            await svc.notify(
                NotificationEvent(
                    event_type=NotificationEventType.WORKFLOW_FAILED,
                    occurred_at=finished_at,
                    workflow_id=workflow_id,
                    job_id=job_id,
                )
            )
            for task_id, execution_id, task_finished in failed:
                await svc.notify(
                    NotificationEvent(
                        event_type=NotificationEventType.JOB_FAILED,
                        occurred_at=task_finished or finished_at,
                        workflow_id=workflow_id,
                        job_id=job_id,
                        execution_id=execution_id,
                        job_task_id=task_id,
                    )
                )
        except Exception:  # noqa: BLE001 - notificação nunca altera o resultado do Job
            logger.exception(
                "falha ao acionar notificações", extra={"job_id": str(job_id)}
            )

    # ── helpers ────────────────────────────────────────────────────────────
    async def _launch_task(
        self, session: Any, job: Job, jt: JobTask, wtask: Any
    ) -> uuid.UUID | None:
        version_id = await NotebookRepository(session).current_version_id(
            wtask.notebook_id
        )
        if version_id is None:
            jt.status = JobTaskStatus.FAILED
            jt.finished_at = _now()
            jt.error_message = "notebook da tarefa não encontrado"
            await self._log(
                session, job.id, jt.id, f"tarefa '{wtask.name}' → FAILED (sem notebook)"
            )
            return None

        params = {**(wtask.parameters or {}), **(job.parameters or {})}
        execution = await ExecutionService(session).create_raw(
            version_id,
            parameters=params,
            retry_policy=wtask.retry_policy or None,
            timeout_s=wtask.timeout_s,
        )
        jt.execution_id = execution.id
        jt.status = JobTaskStatus.QUEUED
        jt.attempt = 1
        jt.started_at = None
        jt.finished_at = None
        jt.error_message = None
        await session.flush()
        await self._log(session, job.id, jt.id, f"tarefa '{wtask.name}' enfileirada")
        return execution.id

    async def _finalize(self, session: Any, job: Job, status: JobStatus) -> None:
        job.status = status
        job.finished_at = _now()
        if job.started_at is not None:
            job.duration_ms = int(
                (job.finished_at - job.started_at).total_seconds() * 1000
            )
        await self._log(session, job.id, None, f"job finalizado: {status.value}")
        await session.flush()

    async def _log(
        self, session: Any, job_id: uuid.UUID, job_task_id: uuid.UUID | None, message: str
    ) -> None:
        seq = int(await self.redis.incr(self.settings.job_seq_key(str(job_id))))
        session.add(
            JobLog(
                job_id=job_id,
                job_task_id=job_task_id,
                ts=_now(),
                level=LogLevel.INFO,
                message=message,
                attempt=1,
                seq=seq,
            )
        )
        await self._publish(
            job_id,
            make_event(
                "log",
                seq=seq,
                message=message,
                job_task_id=str(job_task_id) if job_task_id else None,
            ),
        )

    async def _is_cancelling(self, job_id: uuid.UUID) -> bool:
        return bool(
            await self.redis.exists(self.settings.job_cancel_key(str(job_id)))
        )

    async def _publish(self, job_id: uuid.UUID, event: dict[str, Any]) -> None:
        try:
            await publish_job_event(self.redis, str(job_id), event)
        except Exception:  # noqa: BLE001 - eventos são best-effort
            logger.debug("falha ao publicar evento de job", extra={"job_id": str(job_id)})


def _deps_of(edges: list[tuple[uuid.UUID, uuid.UUID]]) -> dict[uuid.UUID, set[uuid.UUID]]:
    result: dict[uuid.UUID, set[uuid.UUID]] = defaultdict(set)
    for src, dst in edges:
        result[dst].add(src)
    return result


def _map_exec_status(status: ExecutionStatus) -> JobTaskStatus:
    if status == ExecutionStatus.SUCCESS:
        return JobTaskStatus.SUCCESS
    if status == ExecutionStatus.CANCELLED:
        return JobTaskStatus.CANCELLED
    return JobTaskStatus.FAILED
