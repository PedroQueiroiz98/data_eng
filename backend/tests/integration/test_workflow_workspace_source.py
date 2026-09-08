"""Workflow apontando para um notebook = arquivo do Workspace (source=WORKSPACE)."""

from __future__ import annotations

import pytest

from tests.conftest import requires_services
from tests.integration.helpers import drive_job, make_workspace_notebook

pytestmark = [pytest.mark.asyncio, requires_services]


async def _workflow(client, name: str) -> str:
    resp = await client.post("/api/workflows", json={"name": name})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def test_save_graph_validates_workspace_notebook_and_runs(client) -> None:
    ws_id, path = await make_workspace_notebook(client, source="print('hi')")
    wf = await _workflow(client, "wf-ws-src")

    graph = {
        "tasks": [
            {
                "key": "t1",
                "name": "nb",
                "type": "NOTEBOOK",
                "workspace_id": ws_id,
                "notebook_path": path,
                "ui_position": {"x": 0, "y": 0},
            }
        ],
        "dependencies": [],
    }
    resp = await client.put(f"/api/workflows/{wf}/graph", json=graph)
    assert resp.status_code == 200, resp.text
    task = resp.json()["tasks"][0]
    assert task["workspace_id"] == ws_id
    assert task["notebook_path"] == path

    job = (await client.post(f"/api/workflows/{wf}/run", json={})).json()
    assert await drive_job(job["id"]) == "SUCCESS"

    detail = (await client.get(f"/api/jobs/{job['id']}")).json()
    exec_id = detail["tasks"][0]["execution_id"]
    ex = (await client.get(f"/api/executions/{exec_id}")).json()
    assert ex["source"] == "WORKSPACE"
    assert ex["notebook_path"] == path


async def test_save_graph_rejects_missing_workspace_notebook(client) -> None:
    ws_id, _ = await make_workspace_notebook(client)
    wf = await _workflow(client, "wf-ws-missing")
    graph = {
        "tasks": [
            {
                "key": "t1",
                "name": "nb",
                "type": "NOTEBOOK",
                "workspace_id": ws_id,
                "notebook_path": "notebooks/does_not_exist.ipynb",
                "ui_position": {"x": 0, "y": 0},
            }
        ],
        "dependencies": [],
    }
    resp = await client.put(f"/api/workflows/{wf}/graph", json=graph)
    assert resp.status_code == 422, resp.text
    assert "não encontrado" in resp.json()["error"]["message"].lower()


async def test_file_paths_endpoint(client) -> None:
    ws_id, nb_path = await make_workspace_notebook(client)
    put = await client.put(
        f"/api/workspaces/{ws_id}/file",
        params={"path": "data/x.csv"},
        json={"text": "a,b\n1,2\n"},
    )
    assert put.status_code == 200
    r = await client.get(
        f"/api/workspaces/{ws_id}/file/paths",
        params={"path": "data/x.csv", "from_path": nb_path},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["workspace_path"].endswith("/data/x.csv")
    assert body["name"] == "x.csv"
    assert body["read_example"] == 'pd.read_csv("../data/x.csv")'
