from __future__ import annotations

import pytest

from nbplatform.queue.redis_client import get_redis
from nbplatform.worker.execution_manager import ExecutionManager, cleanup_workdir
from tests.conftest import requires_services
from tests.integration.helpers import drive_job, make_notebook, make_workflow, notebook_content

pytestmark = [pytest.mark.asyncio, requires_services]


async def _notebook(client) -> str:
    resp = await client.post("/api/notebooks", json={"name": "exec-me"})
    assert resp.status_code == 201
    return resp.json()["id"]


async def test_execute_enqueues_execution(client) -> None:
    nb_id = await _notebook(client)
    resp = await client.post(
        f"/api/notebooks/{nb_id}/execute", json={"parameters": {"environment": "dev"}}
    )
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["status"] == "QUEUED"
    assert body["parameters"] == {"environment": "dev"}
    assert body["attempt"] == 1

    detail = (await client.get(f"/api/executions/{body['id']}")).json()
    assert detail["id"] == body["id"]
    assert detail["has_output"] is False

    logs = (await client.get(f"/api/executions/{body['id']}/logs")).json()
    assert logs == []

    out = await client.get(f"/api/executions/{body['id']}/output")
    assert out.status_code == 404


async def test_execute_is_idempotent_by_key(client) -> None:
    nb_id = await _notebook(client)
    first = await client.post(
        f"/api/notebooks/{nb_id}/execute", json={"idempotency_key": "run-42"}
    )
    second = await client.post(
        f"/api/notebooks/{nb_id}/execute", json={"idempotency_key": "run-42"}
    )
    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["id"] == second.json()["id"]


async def test_execute_missing_notebook_is_404(client) -> None:
    resp = await client.post(
        "/api/notebooks/00000000-0000-0000-0000-000000000000/execute", json={}
    )
    assert resp.status_code == 404


async def test_list_filters_by_status(client) -> None:
    nb_id = await _notebook(client)
    await client.post(f"/api/notebooks/{nb_id}/execute", json={})
    queued = (await client.get("/api/executions?status=QUEUED&limit=200")).json()
    assert all(e["status"] == "QUEUED" for e in queued)
    assert len(queued) >= 1


async def test_delete_queued_execution_cancels_then_removes(client) -> None:
    nb_id = await _notebook(client)
    ex = (await client.post(f"/api/notebooks/{nb_id}/execute", json={})).json()
    assert ex["status"] == "QUEUED"
    resp = await client.delete(f"/api/executions/{ex['id']}")
    assert resp.status_code == 204, resp.text
    assert (await client.get(f"/api/executions/{ex['id']}")).status_code == 404


async def test_delete_terminal_standalone_execution(client) -> None:
    nb_id = await _notebook(client)
    ex_id = (await client.post(f"/api/notebooks/{nb_id}/execute", json={})).json()["id"]
    try:
        status = await ExecutionManager(get_redis(), worker_id="test-del").run(ex_id, attempt=1)
    finally:
        cleanup_workdir(ex_id)
    assert status.value == "SUCCESS"

    assert (await client.delete(f"/api/executions/{ex_id}")).status_code == 204
    assert (await client.get(f"/api/executions/{ex_id}")).status_code == 404


async def test_delete_execution_that_belongs_to_a_job_is_409(client) -> None:
    nb = await make_notebook(client, "job-nb", notebook_content("print('ok')"))
    wf = await make_workflow(
        client, "wf-del-exec", [{"key": "a", "name": "A", "notebook_id": nb}], []
    )
    job = (await client.post(f"/api/workflows/{wf}/run", json={})).json()
    assert await drive_job(job["id"]) == "SUCCESS"

    detail = (await client.get(f"/api/jobs/{job['id']}")).json()
    exec_id = detail["tasks"][0]["execution_id"]
    assert exec_id

    resp = await client.delete(f"/api/executions/{exec_id}")
    assert resp.status_code == 409
    assert "job" in resp.json()["error"]["message"].lower()
