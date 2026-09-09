from __future__ import annotations

from typing import Any

import httpx
import pytest

from nbplatform.domain.assistant import AssistantResult
from nbplatform.services.assistant.registry import AssistantProviderRegistry
from tests.conftest import requires_services

pytestmark = requires_services


class _FakeProvider:
    provider_type = "OPENAI"

    def validate_config(self, config: dict[str, Any], *, has_secret: bool) -> None:
        return None

    def summary(self, config: dict[str, Any]) -> str:
        return "fake @ test"

    async def complete(self, req: Any, target: Any, *, timeout_s: float) -> AssistantResult:
        return AssistantResult.success("print('ok')", model="fake-1", usage={"prompt_tokens": 3})

    def supports_stream(self) -> bool:
        return False

    async def stream(self, req: Any, target: Any, *, timeout_s: float):  # type: ignore[no-untyped-def]
        yield "print('ok')"


@pytest.fixture(autouse=True)
def _fake_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    reg = AssistantProviderRegistry([_FakeProvider()])
    for mod in (
        "nbplatform.services.assistant.service",
        "nbplatform.services.assistant.provider_admin",
    ):
        monkeypatch.setattr(f"{mod}.default_registry", lambda **_k: reg)


async def _create(client: httpx.AsyncClient, **over: Any) -> dict[str, Any]:
    body = {
        "name": over.get("name", "openai-test"),
        "description": None,
        "provider_type": "OPENAI",
        "enabled": True,
        "is_default": True,
        "configuration": {"model": "gpt-4o-mini"},
        "secret": "sk-test",
        **over,
    }
    r = await client.post("/api/assistant/providers", json=body)
    assert r.status_code == 201, r.text
    return r.json()


async def _cleanup(client: httpx.AsyncClient) -> None:
    for p in (await client.get("/api/assistant/providers")).json():
        await client.delete(f"/api/assistant/providers/{p['id']}")


async def test_providers_crud_is_admin_only(client: httpx.AsyncClient) -> None:
    await _cleanup(client)
    saved = client.headers.pop("Authorization", None)
    try:
        r = await client.post("/api/assistant/providers", json={"name": "x"})
        assert r.status_code == 401
    finally:
        if saved:
            client.headers["Authorization"] = saved


async def test_availability_and_run_and_inline(client: httpx.AsyncClient) -> None:
    await _cleanup(client)
    # sem provider
    av = (await client.get("/api/assistant/availability")).json()
    assert av["configured"] is False
    r = await client.post(
        "/api/assistant/run",
        json={
            "task": "EXPLAIN",
            "context": {"cells": ["print(1)"], "active_cell_index": 0},
        },
    )
    assert r.status_code == 200 and r.json()["ok"] is False

    await _create(client)
    av = (await client.get("/api/assistant/availability")).json()
    assert av["configured"] is True and av["provider_type"] == "OPENAI"

    r = await client.post(
        "/api/assistant/run",
        json={
            "task": "GENERATE",
            "context": {"cells": ["import pandas as pd", "df.head()"], "active_cell_index": 1},
            "instruction": "mostre as 10 primeiras linhas",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True and "print" in body["text"]
    assert body["interaction_id"]

    r = await client.post(
        "/api/assistant/inline",
        json={"context": {"cells": ["df['x'] = "], "active_cell_index": 0}},
    )
    assert r.status_code == 200 and r.json()["completion"]

    hist = (await client.get("/api/assistant/interactions")).json()
    assert hist["total"] >= 1
    await _cleanup(client)


async def test_provider_test_endpoint(client: httpx.AsyncClient) -> None:
    await _cleanup(client)
    p = await _create(client)
    r = await client.post(f"/api/assistant/providers/{p['id']}/test")
    assert r.status_code == 200 and r.json()["ok"] is True
    await _cleanup(client)


async def test_enabling_second_provider_clears_default(client: httpx.AsyncClient) -> None:
    await _cleanup(client)
    a = await _create(client, name="a", is_default=True)
    b = await _create(client, name="b", is_default=True)
    providers = {p["name"]: p for p in (await client.get("/api/assistant/providers")).json()}
    assert providers["b"]["is_default"] is True
    assert providers["a"]["is_default"] is False
    assert {a["id"], b["id"]}  # usa as vars
    await _cleanup(client)
