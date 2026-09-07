from __future__ import annotations

import uuid

import pytest

from nbplatform.db.session import session_scope
from nbplatform.domain.enums import JobStatus, JobTaskStatus
from nbplatform.repositories.job_repository import JobRepository
from tests.conftest import requires_services
from tests.integration.helpers import (
    drive_job,
    make_notebook,
    make_workflow,
    notebook_content,
)

pytestmark = [pytest.mark.asyncio, requires_services]


async def _task(key: str, nb: str, **extra) -> dict:
    return {"key": key, "name": key.title(), "notebook_id": nb, **extra}


async def _job_tasks(job_id: str) -> dict[str, JobTaskStatus]:
    async with session_scope() as session:
        job = await JobRepository(session).get_with_tasks(uuid.UUID(job_id))
        assert job is not None
        wf_tasks = {}  # workflow_task_id -> name via graph
        from nbplatform.repositories.workflow_repository import WorkflowRepository

        wf = await WorkflowRepository(session).get_with_graph(job.workflow_id)
        wf_tasks = {t.id: t.name for t in wf.tasks}
        return {wf_tasks[t.workflow_task_id]: t.status for t in job.tasks}


async def test_linear_dag_all_succeed(client) -> None:
    nb = await make_notebook(client, "ok", notebook_content("print('ok', value)"))
    wf = await make_workflow(
        client,
        "A-B-C",
        [await _task("a", nb), await _task("b", nb), await _task("c", nb)],
        [{"from_key": "a", "to_key": "b"}, {"from_key": "b", "to_key": "c"}],
    )
    job = (await client.post(f"/api/workflows/{wf}/run", json={})).json()
    status = await drive_job(job["id"])
    assert status == JobStatus.SUCCESS
    assert await _job_tasks(job["id"]) == {
        "A": JobTaskStatus.SUCCESS,
        "B": JobTaskStatus.SUCCESS,
        "C": JobTaskStatus.SUCCESS,
    }


async def test_failed_middle_task_skips_downstream(client) -> None:
    ok = await make_notebook(client, "ok2", notebook_content("print('ok')"))
    bad = await make_notebook(client, "bad", notebook_content("raise RuntimeError('boom')"))
    wf = await make_workflow(
        client,
        "A-Bfail-C",
        [
            await _task("a", ok),
            await _task("b", bad),
            await _task("c", ok),
        ],
        [{"from_key": "a", "to_key": "b"}, {"from_key": "b", "to_key": "c"}],
    )
    job = (await client.post(f"/api/workflows/{wf}/run", json={})).json()
    status = await drive_job(job["id"])
    assert status == JobStatus.FAILED
    tasks = await _job_tasks(job["id"])
    assert tasks["A"] == JobTaskStatus.SUCCESS
    assert tasks["B"] == JobTaskStatus.FAILED
    assert tasks["C"] == JobTaskStatus.SKIPPED


async def test_parallel_independent_tasks(client) -> None:
    nb = await make_notebook(client, "par", notebook_content("print('x')"))
    wf = await make_workflow(
        client,
        "A-B->C",
        [await _task("a", nb), await _task("b", nb), await _task("c", nb)],
        [{"from_key": "a", "to_key": "c"}, {"from_key": "b", "to_key": "c"}],
    )
    job = (await client.post(f"/api/workflows/{wf}/run", json={})).json()

    # após o start, A e B devem estar enfileiradas juntas (sem dependência entre si)
    initial = await _job_tasks(job["id"])
    assert initial["A"] in (JobTaskStatus.QUEUED, JobTaskStatus.RUNNING)
    assert initial["B"] in (JobTaskStatus.QUEUED, JobTaskStatus.RUNNING)
    assert initial["C"] == JobTaskStatus.PENDING

    status = await drive_job(job["id"])
    assert status == JobStatus.SUCCESS
    assert all(s == JobTaskStatus.SUCCESS for s in (await _job_tasks(job["id"])).values())
