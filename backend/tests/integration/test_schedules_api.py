from __future__ import annotations

import pytest

from tests.conftest import requires_services
from tests.integration.helpers import make_notebook, make_workflow, notebook_content

pytestmark = [pytest.mark.asyncio, requires_services]


async def _workflow(client) -> str:
    nb = await make_notebook(client, "sn", notebook_content("print(1)"))
    return await make_workflow(
        client, "wf-sched", [{"key": "a", "name": "A", "notebook_id": nb}], []
    )


async def test_crud_lifecycle(client) -> None:
    wf = await _workflow(client)
    resp = await client.post(
        "/api/schedules",
        json={"workflow_id": wf, "cron": "*/10 * * * *", "parameters": {"env": "dev"}},
    )
    assert resp.status_code == 201, resp.text
    sched = resp.json()
    assert sched["enabled"] is True
    assert sched["next_run_at"] is not None

    listing = (await client.get(f"/api/schedules?workflow_id={wf}")).json()
    assert any(s["id"] == sched["id"] for s in listing)

    upd = await client.put(f"/api/schedules/{sched['id']}", json={"enabled": False})
    assert upd.status_code == 200
    assert upd.json()["enabled"] is False
    assert upd.json()["next_run_at"] is None  # desabilitado não agenda

    assert (await client.delete(f"/api/schedules/{sched['id']}")).status_code == 204
    assert (await client.get(f"/api/schedules/{sched['id']}")).status_code == 404


async def test_invalid_cron_rejected(client) -> None:
    wf = await _workflow(client)
    resp = await client.post(
        "/api/schedules", json={"workflow_id": wf, "cron": "banana"}
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"


async def test_unknown_workflow_rejected(client) -> None:
    resp = await client.post(
        "/api/schedules",
        json={
            "workflow_id": "00000000-0000-0000-0000-000000000000",
            "cron": "* * * * *",
        },
    )
    assert resp.status_code == 404
