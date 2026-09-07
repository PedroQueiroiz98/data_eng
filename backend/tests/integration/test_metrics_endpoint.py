from __future__ import annotations

import httpx
import pytest

from nbplatform.api.main import create_app
from tests.conftest import requires_services
from tests.integration.helpers import make_notebook, notebook_content

pytestmark = [pytest.mark.asyncio, requires_services]


async def test_metrics_is_public_and_prometheus_formatted(client) -> None:
    # /metrics não exige token
    app = create_app()
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as anon,
    ):
        resp = await anon.get("/metrics")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/plain")
    body = resp.text
    for name in (
        "nbp_executions_total",
        "nbp_jobs_total",
        "nbp_queue_size",
        "nbp_worker_active",
        "nbp_execution_duration_seconds_sum",
    ):
        assert f"# TYPE {name} " in body


async def test_execution_count_reflected_in_metrics(client) -> None:
    before = _value(await _metrics(client), "nbp_executions_total")

    nb = await make_notebook(client, "m", notebook_content("print(1)"))
    await client.post(f"/api/notebooks/{nb}/execute", json={})

    after = _value(await _metrics(client), "nbp_executions_total")
    assert after == before + 1


async def _metrics(client) -> str:
    return (await client.get("/metrics")).text


def _value(body: str, name: str) -> int:
    for line in body.splitlines():
        if line.startswith(f"{name} "):
            return int(float(line.split()[1]))
    raise AssertionError(f"métrica {name} não encontrada")
