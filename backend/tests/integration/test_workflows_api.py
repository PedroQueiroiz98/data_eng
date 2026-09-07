from __future__ import annotations

import pytest

from tests.conftest import requires_services

pytestmark = [pytest.mark.asyncio, requires_services]


async def _notebook(client, name: str = "wf-nb") -> str:
    return (await client.post("/api/notebooks", json={"name": name})).json()["id"]


async def _workflow(client, name: str = "ETL") -> str:
    resp = await client.post("/api/workflows", json={"name": name})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _graph(nb: str) -> dict:
    return {
        "tasks": [
            {
                "key": "extract",
                "name": "Extract",
                "notebook_id": nb,
                "ui_position": {"x": 0, "y": 0},
            },
            {"key": "transform", "name": "Transform", "notebook_id": nb},
            {"key": "load", "name": "Load", "notebook_id": nb, "max_retries": 3},
        ],
        "dependencies": [
            {"from_key": "extract", "to_key": "transform"},
            {"from_key": "transform", "to_key": "load"},
        ],
    }


async def test_crud_lifecycle(client) -> None:
    wf_id = await _workflow(client)
    detail = (await client.get(f"/api/workflows/{wf_id}")).json()
    assert detail["status"] == "DRAFT"
    assert detail["tasks"] == []

    upd = await client.put(
        f"/api/workflows/{wf_id}", json={"status": "ACTIVE", "description": "pipeline"}
    )
    assert upd.status_code == 200
    assert upd.json()["status"] == "ACTIVE"

    assert (await client.delete(f"/api/workflows/{wf_id}")).status_code == 204
    assert (await client.get(f"/api/workflows/{wf_id}")).status_code == 404


async def test_save_valid_graph(client) -> None:
    wf_id = await _workflow(client)
    nb = await _notebook(client)
    resp = await client.put(f"/api/workflows/{wf_id}/graph", json=_graph(nb))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert {t["name"] for t in body["tasks"]} == {"Extract", "Transform", "Load"}
    assert len(body["dependencies"]) == 2
    load = next(t for t in body["tasks"] if t["name"] == "Load")
    assert load["max_retries"] == 3
    extract = next(t for t in body["tasks"] if t["name"] == "Extract")
    assert extract["ui_position"] == {"x": 0.0, "y": 0.0}


async def test_cycle_is_rejected(client) -> None:
    wf_id = await _workflow(client)
    nb = await _notebook(client)
    graph = _graph(nb)
    graph["dependencies"].append({"from_key": "load", "to_key": "extract"})
    resp = await client.put(f"/api/workflows/{wf_id}/graph", json=graph)
    assert resp.status_code == 422
    assert "ciclo" in resp.json()["error"]["message"]


async def test_unknown_notebook_is_rejected(client) -> None:
    wf_id = await _workflow(client)
    graph = {
        "tasks": [
            {
                "key": "t1",
                "name": "T1",
                "notebook_id": "00000000-0000-0000-0000-000000000000",
            }
        ],
        "dependencies": [],
    }
    resp = await client.put(f"/api/workflows/{wf_id}/graph", json=graph)
    assert resp.status_code == 422
    assert "inexistente" in resp.json()["error"]["message"]


async def test_save_graph_upsert_preserves_ids_and_removes_orphans(client) -> None:
    wf_id = await _workflow(client)
    nb = await _notebook(client)

    first = (await client.put(f"/api/workflows/{wf_id}/graph", json=_graph(nb))).json()
    ids = {t["name"]: t["id"] for t in first["tasks"]}

    # segunda gravação: mantém Extract (por id) e Transform, remove Load, adiciona Report
    second_graph = {
        "tasks": [
            {"key": ids["Extract"], "name": "Extract", "notebook_id": nb},
            {"key": ids["Transform"], "name": "Transform 2", "notebook_id": nb},
            {"key": "report", "name": "Report", "notebook_id": nb},
        ],
        "dependencies": [
            {"from_key": ids["Extract"], "to_key": ids["Transform"]},
            {"from_key": ids["Transform"], "to_key": "report"},
        ],
    }
    second = (await client.put(f"/api/workflows/{wf_id}/graph", json=second_graph)).json()
    by_name = {t["name"]: t for t in second["tasks"]}

    assert set(by_name) == {"Extract", "Transform 2", "Report"}
    assert by_name["Extract"]["id"] == ids["Extract"]  # id preservado
    assert by_name["Transform 2"]["id"] == ids["Transform"]  # id preservado, nome mudou
    assert len(second["dependencies"]) == 2
