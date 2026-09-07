"""Execução de `.ipynb` do Workspace via Papermill (ExecutionSource.WORKSPACE) — Fase 7."""

from __future__ import annotations

import pytest

from nbplatform.domain.enums import ExecutionStatus
from nbplatform.queue.redis_client import get_redis
from nbplatform.worker.execution_manager import ExecutionManager, cleanup_workdir
from tests.conftest import requires_services
from tests.integration.helpers import notebook_content

pytestmark = [pytest.mark.asyncio, requires_services]

# Notebook que usa o workspace_sdk — prova de que WORKSPACE_ROOT foi injetado.
# Obs.: a assinatura do SDK é write_text(data, rel) (data primeiro).
NB = notebook_content(
    "from workspace_sdk import workspace\n"
    "workspace.write_text(f'ok {value}', 'output/from_exec.txt')\n",
    params_source="value = 0\n",
)


async def _run_execution(exec_id: str) -> ExecutionStatus:
    mgr = ExecutionManager(get_redis(), worker_id="test-ws-exec")
    try:
        return await mgr.run(exec_id, attempt=1)
    finally:
        cleanup_workdir(exec_id)


async def test_execute_workspace_notebook_end_to_end(client) -> None:
    wid = (await client.post("/api/workspaces", json={"name": "exec-ws"})).json()["id"]
    w = await client.put(
        f"/api/workspaces/{wid}/file?path=notebooks/run.ipynb", json={"notebook": NB}
    )
    assert w.status_code == 200, w.text

    r = await client.post(
        f"/api/workspaces/{wid}/execute",
        json={"notebook_path": "notebooks/run.ipynb", "parameters": {"value": 7}},
    )
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["source"] == "WORKSPACE"
    assert body["workspace_id"] == wid
    assert body["notebook_path"] == "notebooks/run.ipynb"
    assert body["notebook_version_id"] is None
    exec_id = body["id"]

    assert await _run_execution(exec_id) == ExecutionStatus.SUCCESS

    got = (await client.get(f"/api/executions/{exec_id}")).json()
    assert got["status"] == "SUCCESS"
    assert got["source"] == "WORKSPACE"

    # workspace_sdk escreveu de volta no Workspace → WORKSPACE_ROOT funcionou
    f = await client.get(f"/api/workspaces/{wid}/file?path=output/from_exec.txt")
    assert f.status_code == 200
    assert f.json()["content"].strip() == "ok 7"


async def test_execute_rejects_non_ipynb_and_missing_file(client) -> None:
    wid = (await client.post("/api/workspaces", json={"name": "exec-ws2"})).json()["id"]

    r = await client.post(
        f"/api/workspaces/{wid}/execute", json={"notebook_path": "scripts/x.py"}
    )
    assert r.status_code == 422

    r = await client.post(
        f"/api/workspaces/{wid}/execute", json={"notebook_path": "notebooks/nope.ipynb"}
    )
    assert r.status_code == 404


async def test_execute_requires_editor_role(client) -> None:
    import uuid

    wid = (await client.post("/api/workspaces", json={"name": "exec-ws3"})).json()["id"]
    w = await client.put(
        f"/api/workspaces/{wid}/file?path=notebooks/run.ipynb", json={"notebook": NB}
    )
    assert w.status_code == 200

    email = f"v-{uuid.uuid4().hex[:8]}@x.com"
    reg = await client.post(
        "/api/auth/register",
        json={"email": email, "name": "V", "password": "secret123", "role": "member"},
    )
    uid = reg.json()["id"]
    tok = (
        await client.post(
            "/api/auth/login", json={"email": email, "password": "secret123"}
        )
    ).json()["access_token"]
    await client.put(f"/api/workspaces/{wid}/members/{uid}", json={"role": "VIEWER"})

    r = await client.post(
        f"/api/workspaces/{wid}/execute",
        json={"notebook_path": "notebooks/run.ipynb"},
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r.status_code == 403
