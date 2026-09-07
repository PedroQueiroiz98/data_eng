from __future__ import annotations

import pytest

from tests.conftest import requires_services

pytestmark = [pytest.mark.asyncio, requires_services]


async def test_secret_value_never_returned(client) -> None:
    resp = await client.put("/api/secrets/DB_PASSWORD", json={"value": "hunter2-super"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["key"] == "DB_PASSWORD"
    assert "value" not in body
    assert "ciphertext" not in body
    assert "hunter2-super" not in str(body)

    listing = (await client.get("/api/secrets")).json()
    entry = next(s for s in listing if s["key"] == "DB_PASSWORD")
    assert "value" not in entry

    assert (await client.delete("/api/secrets/DB_PASSWORD")).status_code == 204
    assert (await client.delete("/api/secrets/DB_PASSWORD")).status_code == 404


async def test_variable_crud_returns_value(client) -> None:
    resp = await client.put(
        "/api/variables/ENVIRONMENT", json={"value": "production"}
    )
    assert resp.status_code == 200
    assert resp.json()["value"] == "production"

    listing = (await client.get("/api/variables")).json()
    assert any(v["key"] == "ENVIRONMENT" and v["value"] == "production" for v in listing)

    upd = await client.put("/api/variables/ENVIRONMENT", json={"value": "staging"})
    assert upd.json()["value"] == "staging"

    assert (await client.delete("/api/variables/ENVIRONMENT")).status_code == 204
