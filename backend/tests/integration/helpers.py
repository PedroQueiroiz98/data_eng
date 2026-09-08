"""Helpers compartilhados para testes de integração de Jobs."""

from __future__ import annotations

import uuid

from nbplatform.db.session import session_scope
from nbplatform.domain.enums import JobStatus, JobTaskStatus
from nbplatform.domain.notebook_format import validate_notebook
from nbplatform.models.notebook import Notebook, NotebookVersion
from nbplatform.queue.redis_client import get_redis
from nbplatform.repositories.job_repository import JobRepository
from nbplatform.services.job_orchestrator import JobOrchestrator
from nbplatform.worker.execution_manager import ExecutionManager, cleanup_workdir


def notebook_content(source: str, *, params_source: str = "value = 0\n") -> dict:
    return {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {"kernelspec": {"name": "python3", "display_name": "Python 3"}},
        "cells": [
            {
                "cell_type": "code",
                "metadata": {"tags": ["parameters"]},
                "source": params_source,
                "outputs": [],
                "execution_count": None,
            },
            {
                "cell_type": "code",
                "metadata": {},
                "source": source,
                "outputs": [],
                "execution_count": None,
            },
        ],
    }


async def make_notebook(client, name: str, content: dict) -> str:
    """Cria um Notebook DB (legado) direto no banco.

    O módulo global `/api/notebooks` foi removido; Jobs/Workflows legados ainda
    referenciam `workflow_tasks.notebook_id`, então os testes seguem criando as
    linhas via ORM.
    """
    validated = validate_notebook(content)
    nb_id = uuid.uuid4()
    async with session_scope() as session:
        session.add(Notebook(id=nb_id, name=name, current_version=1))
        session.add(
            NotebookVersion(
                notebook_id=nb_id, version_number=1, content=validated
            )
        )
    return str(nb_id)


_UNIQ = 0


async def make_workspace(client, name: str | None = None) -> str:
    global _UNIQ
    _UNIQ += 1
    resp = await client.post(
        "/api/workspaces", json={"name": name or f"ws-{_UNIQ}-{uuid.uuid4().hex[:6]}"}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def make_workspace_notebook(
    client,
    *,
    source: str = "value = 0\n",
    params_source: str = "value = 0\n",
    path: str = "notebooks/nb.ipynb",
) -> tuple[str, str]:
    """Cria um Workspace + escreve um `.ipynb` nele. Retorna (workspace_id, path)."""
    ws_id = await make_workspace(client)
    resp = await client.put(
        f"/api/workspaces/{ws_id}/file",
        params={"path": path},
        json={"notebook": notebook_content(source, params_source=params_source)},
    )
    assert resp.status_code == 200, resp.text
    return ws_id, path


async def execute_ws_notebook(client, ws_id: str, path: str, **body):
    """`POST /api/workspaces/{id}/execute` — substitui o antigo /api/notebooks/{id}/execute."""
    payload = {"notebook_path": path, **body}
    return await client.post(f"/api/workspaces/{ws_id}/execute", json=payload)


async def make_workflow(client, name: str, tasks: list[dict], deps: list[dict]) -> str:
    wf = (await client.post("/api/workflows", json={"name": name})).json()
    resp = await client.put(
        f"/api/workflows/{wf['id']}/graph", json={"tasks": tasks, "dependencies": deps}
    )
    assert resp.status_code == 200, resp.text
    return wf["id"]


async def drive_job(job_id: str, *, max_rounds: int = 30) -> JobStatus:
    """Roda as execuções pendentes e avança o job até o estado terminal."""
    redis = get_redis()
    orchestrator = JobOrchestrator(redis)
    job_uuid = uuid.UUID(job_id)

    for _ in range(max_rounds):
        async with session_scope() as session:
            job = await JobRepository(session).get_with_tasks(job_uuid)
            assert job is not None
            if job.status in (JobStatus.SUCCESS, JobStatus.FAILED, JobStatus.CANCELLED):
                return job.status
            runnable = [
                (jt.execution_id, jt.status)
                for jt in job.tasks
                if jt.execution_id is not None
                and jt.status in (JobTaskStatus.QUEUED, JobTaskStatus.RUNNING)
            ]

        ran_any = False
        for exec_id, _status in runnable:
            manager = ExecutionManager(redis, worker_id="test-orch")
            try:
                await manager.run(str(exec_id), attempt=1)
            finally:
                cleanup_workdir(str(exec_id))
            ran_any = True

        await orchestrator.sync_and_advance(job_uuid)
        if not ran_any:
            await orchestrator.sync_and_advance(job_uuid)

    raise AssertionError("job não terminou dentro do limite de rounds")
