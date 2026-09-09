"""Execução de `.ipynb` do Workspace único via Papermill (ExecutionSource.WORKSPACE)."""

from __future__ import annotations

import uuid

import pytest

from nbplatform.domain.enums import ExecutionStatus
from nbplatform.queue.redis_client import get_redis
from nbplatform.worker.execution_manager import ExecutionManager, cleanup_workdir
from tests.conftest import requires_services
from tests.integration.helpers import SINGLETON_WORKSPACE_ID, notebook_content

pytestmark = [pytest.mark.asyncio, requires_services]

# Notebook que usa o workspace_sdk — prova de que WORKSPACE_ROOT foi injetado.
NB = notebook_content(
    "from workspace_sdk import workspace\n"
    "workspace.write_text(f'ok {value}', 'out_from_exec.txt')\n",
    params_source="value = 0\n",
)


async def _run_execution(exec_id: str) -> ExecutionStatus:
    mgr = ExecutionManager(get_redis(), worker_id="test-ws-exec")
    try:
        return await mgr.run(exec_id, attempt=1)
    finally:
        cleanup_workdir(exec_id)


async def test_execute_workspace_notebook_end_to_end(client) -> None:
    nb_path = f"run-{uuid.uuid4().hex[:6]}.ipynb"
    w = await client.put(
        "/api/workspace/file", params={"path": nb_path}, json={"notebook": NB}
    )
    assert w.status_code == 200, w.text

    r = await client.post(
        "/api/workspace/execute",
        json={"notebook_path": nb_path, "parameters": {"value": 7}},
    )
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["source"] == "WORKSPACE"
    assert body["workspace_id"] == SINGLETON_WORKSPACE_ID
    assert body["notebook_path"] == nb_path
    assert body["notebook_version_id"] is None
    exec_id = body["id"]

    assert await _run_execution(exec_id) == ExecutionStatus.SUCCESS

    got = (await client.get(f"/api/executions/{exec_id}")).json()
    assert got["status"] == "SUCCESS" and got["source"] == "WORKSPACE"

    # workspace_sdk escreveu de volta em /root → WORKSPACE_ROOT funcionou
    f = await client.get("/api/workspace/file", params={"path": "out_from_exec.txt"})
    assert f.status_code == 200
    assert f.json()["content"].strip() == "ok 7"
    await client.delete("/api/workspace/file", params={"path": "out_from_exec.txt"})
    await client.delete("/api/workspace/file", params={"path": nb_path})


async def test_execute_rejects_non_ipynb_and_missing_file(client) -> None:
    assert (
        await client.post("/api/workspace/execute", json={"notebook_path": "x.py"})
    ).status_code == 422
    assert (
        await client.post(
            "/api/workspace/execute", json={"notebook_path": "nope.ipynb"}
        )
    ).status_code == 404
