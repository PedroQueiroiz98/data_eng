from __future__ import annotations

import pytest

from tests.conftest import requires_services

pytestmark = [pytest.mark.asyncio, requires_services]


async def _make_notebook(client, name: str = "ETL Clientes") -> dict:
    resp = await client.post("/api/notebooks", json={"name": name})
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_create_returns_empty_notebook_with_v1(client) -> None:
    body = await _make_notebook(client)
    assert body["current_version"] == 1
    assert body["version_count"] == 1
    assert body["content"]["nbformat"] == 4
    assert any(
        "parameters" in c.get("metadata", {}).get("tags", [])
        for c in body["content"]["cells"]
    )


async def test_create_with_invalid_content_is_422(client) -> None:
    resp = await client.post(
        "/api/notebooks", json={"name": "ruim", "content": {"cells": [{"x": 1}]}}
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"


async def test_get_missing_is_404(client) -> None:
    resp = await client.get("/api/notebooks/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


async def test_update_metadata_does_not_touch_version(client) -> None:
    nb = await _make_notebook(client)
    resp = await client.put(
        f"/api/notebooks/{nb['id']}", json={"description": "importa clientes do ERP"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["description"] == "importa clientes do ERP"
    assert body["current_version"] == 1
    assert body["version_count"] == 1


async def test_save_version_is_immutable_and_bumps_current(client) -> None:
    nb = await _make_notebook(client)
    nb_id = nb["id"]

    v1_content = nb["content"]
    v2_content = {
        **v1_content,
        "cells": [
            *v1_content["cells"],
            {
                "cell_type": "code",
                "metadata": {},
                "source": "print('novo')",
                "outputs": [],
                "execution_count": None,
            },
        ],
    }

    resp = await client.post(f"/api/notebooks/{nb_id}/versions", json={"content": v2_content})
    assert resp.status_code == 201, resp.text
    assert resp.json()["version_number"] == 2

    detail = (await client.get(f"/api/notebooks/{nb_id}")).json()
    assert detail["current_version"] == 2
    assert detail["version_count"] == 2

    versions = (await client.get(f"/api/notebooks/{nb_id}/versions")).json()
    assert [v["version_number"] for v in versions] == [2, 1]

    v1 = (await client.get(f"/api/notebooks/{nb_id}/versions/1")).json()
    v2 = (await client.get(f"/api/notebooks/{nb_id}/versions/2")).json()
    assert len(v1["content"]["cells"]) + 1 == len(v2["content"]["cells"])


async def test_save_version_invalid_content_is_422(client) -> None:
    nb = await _make_notebook(client)
    resp = await client.post(
        f"/api/notebooks/{nb['id']}/versions", json={"content": {"cells": "nope"}}
    )
    assert resp.status_code == 422


async def test_delete_then_get_is_404(client) -> None:
    nb = await _make_notebook(client)
    assert (await client.delete(f"/api/notebooks/{nb['id']}")).status_code == 204
    assert (await client.get(f"/api/notebooks/{nb['id']}")).status_code == 404


async def test_list_contains_created(client) -> None:
    nb = await _make_notebook(client, name="Lista-me")
    listing = (await client.get("/api/notebooks?limit=200")).json()
    assert any(item["id"] == nb["id"] for item in listing)
