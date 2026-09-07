from __future__ import annotations

import pytest

from tests.conftest import requires_services
from tests.integration.helpers import make_notebook, make_workflow, notebook_content

pytestmark = [pytest.mark.asyncio, requires_services]


async def _workflow(client) -> str:
    nb = await make_notebook(client, "jn", notebook_content("print('hi')"))
    return await make_workflow(
        client,
        "wf",
        [
            {"key": "a", "name": "A", "notebook_id": nb},
            {"key": "b", "name": "B", "notebook_id": nb},
        ],
        [{"from_key": "a", "to_key": "b"}],
    )


async def test_run_creates_job_and_tasks(client) -> None:
    wf = await _workflow(client)
    resp = await client.post(f"/api/workflows/{wf}/run", json={"parameters": {"env": "dev"}})
    assert resp.status_code == 202, resp.text
    job = resp.json()
    assert job["status"] == "RUNNING"
    assert job["trigger_type"] == "MANUAL"

    detail = (await client.get(f"/api/jobs/{job['id']}")).json()
    assert detail["workflow_name"] == "wf"
    assert {t["name"] for t in detail["tasks"]} == {"A", "B"}
    a = next(t for t in detail["tasks"] if t["name"] == "A")
    b = next(t for t in detail["tasks"] if t["name"] == "B")
    assert a["status"] in ("QUEUED", "RUNNING")  # sem dependência
    assert b["status"] == "PENDING"  # espera A

    logs = (await client.get(f"/api/jobs/{job['id']}/logs")).json()
    assert any("job iniciado" in log_["message"] for log_ in logs)

    listing = (await client.get(f"/api/jobs?workflow_id={wf}")).json()
    assert any(j["id"] == job["id"] for j in listing)


async def test_cancel_job_is_idempotent(client) -> None:
    wf = await _workflow(client)
    job = (await client.post(f"/api/workflows/{wf}/run", json={})).json()

    first = await client.post(f"/api/jobs/{job['id']}/cancel")
    assert first.status_code == 200
    second = await client.post(f"/api/jobs/{job['id']}/cancel")
    assert second.status_code == 200

    detail = (await client.get(f"/api/jobs/{job['id']}")).json()
    # tarefas pendentes viram CANCELLED; o job settla como CANCELLED
    assert detail["status"] in ("CANCELLED", "RUNNING")


async def test_retry_requires_terminal_failed_job(client) -> None:
    wf = await _workflow(client)
    job = (await client.post(f"/api/workflows/{wf}/run", json={})).json()
    resp = await client.post(f"/api/jobs/{job['id']}/retry")
    assert resp.status_code == 409  # ainda RUNNING
