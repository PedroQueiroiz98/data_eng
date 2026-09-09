from __future__ import annotations

import httpx
import pytest

from tests.conftest import requires_services

pytestmark = requires_services


async def test_health_endpoint(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/lsp/health")
    assert r.status_code == 200
    body = r.json()
    assert body["engine"] == "jedi"
    assert body["enabled"] is True


async def test_completions_endpoint_notebook_context(client: httpx.AsyncClient) -> None:
    r = await client.post(
        "/api/lsp/completions",
        json={
            "cells": ["clientes = []", "clientes."],
            "cell_index": 1,
            "line": 0,
            "column": 9,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    labels = {i["label"] for i in body["items"]}
    assert "append" in labels


async def test_diagnostics_endpoint_flags_undefined_name(client: httpx.AsyncClient) -> None:
    r = await client.post(
        "/api/lsp/diagnostics",
        json={"cells": ["x = 1", "print(does_not_exist)"]},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert any(
        d["severity"] == "error" and d["cell_index"] == 1 for d in body["items"]
    )


async def test_definition_endpoint_points_to_cell(client: httpx.AsyncClient) -> None:
    r = await client.post(
        "/api/lsp/definition",
        json={
            "cells": ["def helper():\n    return 1", "helper()"],
            "cell_index": 1,
            "line": 0,
            "column": 2,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["locations"]
    assert body["locations"][0]["cell_index"] == 0
    assert body["locations"][0]["external"] is False


async def test_auth_required(client: httpx.AsyncClient) -> None:
    saved = client.headers.pop("Authorization", None)
    try:
        r = await client.post(
            "/api/lsp/completions",
            json={"cells": ["x"], "cell_index": 0, "line": 0, "column": 1},
        )
        assert r.status_code == 401
    finally:
        if saved is not None:
            client.headers["Authorization"] = saved


@pytest.mark.parametrize("name,expected_module", [("DataFrame", "pandas"), ("Path", "pathlib")])
async def test_auto_import_endpoint(
    client: httpx.AsyncClient, name: str, expected_module: str
) -> None:
    r = await client.post("/api/lsp/auto-import", json={"name": name})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert any(expected_module in s["module"] for s in body["suggestions"])


async def test_resolve_endpoint_returns_doc(client: httpx.AsyncClient) -> None:
    r = await client.post(
        "/api/lsp/resolve",
        json={
            "cells": ["def greet(name):\n    '''Say hi.'''\n    return name", "greet"],
            "cell_index": 1,
            "line": 0,
            "column": 5,
            "label": "greet",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert "hi" in body["documentation"].lower()


async def test_completions_with_bogus_session_id_still_ok(client: httpx.AsyncClient) -> None:
    r = await client.post(
        "/api/lsp/completions",
        json={
            "cells": ["clientes = []", "clientes."],
            "cell_index": 1,
            "line": 0,
            "column": 9,
            "session_id": "not-a-real-session",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert "append" in {i["label"] for i in body["items"]}
    assert body["took_ms"] < 2500
