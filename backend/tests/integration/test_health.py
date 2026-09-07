from __future__ import annotations

import pytest

from tests.conftest import requires_services

pytestmark = pytest.mark.asyncio


async def test_health_is_liveness_only(client) -> None:
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@requires_services
async def test_ready_reports_all_checks(client) -> None:
    resp = await client.get("/ready")
    body = resp.json()

    assert set(body["checks"]) == {"postgres", "redis", "worker", "scheduler"}
    assert body["checks"]["postgres"]["ok"] is True
    assert body["checks"]["redis"]["ok"] is True

    all_ok = all(c["ok"] for c in body["checks"].values())
    assert (resp.status_code == 200) is all_ok
    assert (resp.status_code == 503) is (not all_ok)
    assert body["status"] == ("ok" if all_ok else "degraded")
