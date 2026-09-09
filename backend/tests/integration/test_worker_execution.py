from __future__ import annotations

import json
import uuid

import pytest

from nbplatform.domain.enums import ExecutionStatus
from nbplatform.queue.redis_client import get_redis
from nbplatform.worker.execution_manager import ExecutionManager, cleanup_workdir
from tests.conftest import requires_services
from tests.integration.helpers import execute_ws_notebook, make_workspace

pytestmark = [pytest.mark.asyncio, requires_services]


def _notebook(cells_source: list[tuple[str, list[str]]]) -> dict:
    cells = []
    for kind_tags, src in cells_source:
        tags = kind_tags.split(",")[1:]
        cells.append(
            {
                "cell_type": "code",
                "source": "".join(src) if isinstance(src, list) else src,
                "metadata": {"tags": tags} if tags else {},
                "outputs": [],
                "execution_count": None,
            }
        )
    return {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {"kernelspec": {"name": "python3", "display_name": "Python 3"}},
        "cells": cells,
    }


async def _prepare(client, content: dict) -> tuple[str, str]:
    ws_id = await make_workspace(client)
    path = "notebooks/w.ipynb"
    resp = await client.put(
        "/api/workspace/file",
        params={"path": path},
        json={"notebook": content},
    )
    assert resp.status_code == 200, resp.text
    return ws_id, path


def client_json(resp):
    assert resp.status_code < 400, resp.text
    return resp.json()


async def _run_execution(client, target: tuple[str, str], parameters: dict) -> str:
    ws_id, path = target
    body = client_json(
        await execute_ws_notebook(client, ws_id, path, parameters=parameters)
    )
    exec_id = body["id"]
    manager = ExecutionManager(get_redis(), worker_id="test-worker")
    try:
        await manager.run(exec_id, attempt=1)
    finally:
        cleanup_workdir(exec_id)
    return exec_id


async def test_successful_run_injects_params_and_stores_output(client) -> None:
    content = _notebook(
        [
            ("code,parameters", 'msg = "default"\n'),
            ("code", 'print(f"got {msg}")\n'),
        ]
    )
    target = await _prepare(client, content)
    exec_id = await _run_execution(client, target, {"msg": "hello"})

    detail = client_json(await client.get(f"/api/executions/{exec_id}"))
    assert detail["status"] == ExecutionStatus.SUCCESS
    assert detail["duration_ms"] is not None
    assert detail["has_output"] is True
    assert detail["worker_id"] == "test-worker"

    out = client_json(await client.get(f"/api/executions/{exec_id}/output"))
    printed = json.dumps(out)
    assert "got hello" in printed

    logs = client_json(await client.get(f"/api/executions/{exec_id}/logs"))
    assert len(logs) >= 1
    assert [log_["seq"] for log_ in logs] == sorted(log_["seq"] for log_ in logs)


async def test_failing_notebook_marks_failed_with_error(client) -> None:
    content = _notebook([("code", 'raise ValueError("boom")\n')])
    target = await _prepare(client, content)
    exec_id = await _run_execution(client, target, {})

    detail = client_json(await client.get(f"/api/executions/{exec_id}"))
    assert detail["status"] == ExecutionStatus.FAILED
    assert detail["error_code"] == "NOTEBOOK_ERROR"
    assert "boom" in (detail["error_message"] or "")
    # output.ipynb ainda é persistido para inspeção
    assert detail["has_output"] is True


async def test_run_ignored_when_not_queued(client) -> None:
    # execução inexistente → manager retorna CANCELLED sem explodir
    manager = ExecutionManager(get_redis(), worker_id="test-worker")
    status = await manager.run(str(uuid.uuid4()), attempt=1)
    assert status == ExecutionStatus.CANCELLED
