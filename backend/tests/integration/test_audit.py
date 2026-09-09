from __future__ import annotations

import pytest

from tests.conftest import requires_services

pytestmark = [pytest.mark.asyncio, requires_services]


async def test_workspace_file_op_is_audited(client) -> None:
    # Não há mais criação de Workspace; auditamos uma operação de arquivo em /root.
    import uuid

    path = f"audit-{uuid.uuid4().hex[:8]}.txt"
    await client.put("/api/workspace/file", params={"path": path}, json={"text": "x"})

    logs = (await client.get("/api/audit-logs?limit=200")).json()
    entry = next(
        (log_ for log_ in logs if log_["action"] == "WORKSPACE_FS_WRITE"),
        None,
    )
    assert entry is not None
    assert entry["resource_type"] == "workspace"
    assert entry["user_id"] is not None
    await client.delete("/api/workspace/file", params={"path": path})


async def test_login_is_audited(client) -> None:
    logs = (await client.get("/api/audit-logs?limit=500")).json()
    assert any(log_["action"] == "LOGIN" for log_ in logs)
