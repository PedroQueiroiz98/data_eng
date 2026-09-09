from __future__ import annotations

import uuid
from typing import Any

import pytest

from nbplatform.domain.assistant import AssistantRequest, AssistantResult, AssistantTask
from nbplatform.services.assistant.registry import AssistantProviderRegistry
from nbplatform.services.assistant.service import AssistantService

KEY = "iY0uDAIk3AqhPlmaVTZOGf-Bajj5kjmIDRZiwqRLvDc="


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SECRET_ENCRYPTION_KEY", KEY)
    from nbplatform.core.config import get_settings

    get_settings.cache_clear()

    async def _empty(self: Any) -> dict[str, str]:
        return {}

    monkeypatch.setattr(
        "nbplatform.services.secret_service.SecretService.resolve_all", _empty
    )
    yield
    get_settings.cache_clear()


class _FakeProvider:
    provider_type = "OPENAI"

    def __init__(self, result: AssistantResult) -> None:
        self._result = result

    def validate_config(self, config: dict[str, Any], *, has_secret: bool) -> None: ...
    def summary(self, config: dict[str, Any]) -> str:
        return "fake"

    async def complete(
        self, req: AssistantRequest, target: Any, *, timeout_s: float
    ) -> AssistantResult:
        return self._result

    def supports_stream(self) -> bool:
        return True

    async def stream(self, req: AssistantRequest, target: Any, *, timeout_s: float):  # type: ignore[no-untyped-def]
        for piece in ["he", "llo"]:
            yield piece


class _Row:
    def __init__(self) -> None:
        self.id = uuid.uuid4()
        self.provider_type = "OPENAI"
        self.configuration_json: dict[str, Any] = {"model": "gpt-4o-mini"}
        self.secret_ct = None


def _svc(monkeypatch: pytest.MonkeyPatch, *, provider: Any, row: Any) -> AssistantService:
    async def _default_provider(self: Any) -> Any:
        return row

    captured: list[dict[str, Any]] = []

    async def _create_interaction(self: Any, **fields: Any) -> uuid.UUID:
        captured.append(fields)
        return uuid.uuid4()

    monkeypatch.setattr(
        "nbplatform.repositories.assistant_repository.AssistantRepository.default_provider",
        _default_provider,
    )
    monkeypatch.setattr(
        "nbplatform.repositories.assistant_repository.AssistantRepository.create_interaction",
        _create_interaction,
    )
    reg = AssistantProviderRegistry([provider]) if provider else AssistantProviderRegistry([])
    svc = AssistantService(object(), None, registry=reg)  # type: ignore[arg-type]
    svc._captured = captured  # type: ignore[attr-defined]
    return svc


_CTX = {"cells": ["import pandas as pd", "df.head()"], "active_cell_index": 1}


async def test_run_without_provider_returns_not_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _none(self: Any) -> Any:
        return None

    monkeypatch.setattr(
        "nbplatform.repositories.assistant_repository.AssistantRepository.default_provider",
        _none,
    )
    svc = AssistantService(object(), None)  # type: ignore[arg-type]
    r = await svc.run(AssistantTask.EXPLAIN, **_CTX)
    assert r.ok is False
    assert r.error == "no provider configured"
    assert await svc.inline_complete(**_CTX) == ""


async def test_run_records_interaction(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _FakeProvider(
        AssistantResult.success("print(1)", model="gpt-4o-mini", usage={"prompt_tokens": 5})
    )
    svc = _svc(monkeypatch, provider=provider, row=_Row())
    r = await svc.run(AssistantTask.GENERATE, instruction="faça algo", **_CTX)
    assert r.ok
    assert r.text == "print(1)"
    assert r.interaction_id
    rec = svc._captured[0]  # type: ignore[attr-defined]
    assert rec["ok"] is True
    assert rec["completion_chars"] == len("print(1)")
    assert rec["result_text"] == "print(1)"  # store_result_text default on


async def test_inline_uses_budget_and_strips_fences(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _FakeProvider(AssistantResult.success("```python\ndf['x'].astype(int)\n```"))
    svc = _svc(monkeypatch, provider=provider, row=_Row())
    out = await svc.inline_complete(**_CTX, cursor_line=0, cursor_column=0)
    assert "```" not in out
    assert "astype(int)" in out


async def test_stream_yields_deltas_then_done(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _FakeProvider(AssistantResult.success(""))
    svc = _svc(monkeypatch, provider=provider, row=_Row())
    frames = [f async for f in svc.stream(AssistantTask.CHAT, instruction="oi", **_CTX)]
    assert [f.get("delta") for f in frames[:2]] == ["he", "llo"]
    assert frames[-1]["done"] is True
    assert frames[-1]["error"] is None


async def test_provider_exception_is_caught(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Boom(_FakeProvider):
        async def complete(self, *a: Any, **k: Any) -> AssistantResult:
            raise RuntimeError("kaboom")

    svc = _svc(monkeypatch, provider=_Boom(AssistantResult.success("")), row=_Row())
    r = await svc.run(AssistantTask.FIX, **_CTX)
    assert r.ok is False
    assert "kaboom" in (r.error or "")
