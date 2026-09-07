from __future__ import annotations

import pytest

from tests.conftest import requires_services

pytestmark = [pytest.mark.asyncio, requires_services]


async def test_notebook_creation_is_audited(client) -> None:
    nb = (await client.post("/api/notebooks", json={"name": "audited"})).json()

    logs = (await client.get("/api/audit-logs?limit=200")).json()
    entry = next(
        (
            log_
            for log_ in logs
            if log_["action"] == "CREATE_NOTEBOOK" and log_["resource_id"] == nb["id"]
        ),
        None,
    )
    assert entry is not None
    assert entry["resource_type"] == "notebook"
    assert entry["user_id"] is not None


async def test_login_is_audited(client) -> None:
    logs = (await client.get("/api/audit-logs?limit=500")).json()
    assert any(log_["action"] == "LOGIN" for log_ in logs)
