from __future__ import annotations

import pytest

from tests.conftest import requires_services

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
