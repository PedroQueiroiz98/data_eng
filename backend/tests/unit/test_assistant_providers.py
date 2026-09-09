from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from nbplatform.domain.assistant import AssistantRequest, AssistantTask, ChatMessage
from nbplatform.services.assistant.providers import (
    AzureOpenAIAssistantProvider,
    OllamaAssistantProvider,
    OpenAIAssistantProvider,
    ResolvedAssistant,
)
from nbplatform.services.assistant.providers.base import ConfigError

_CAPTURED: dict[str, Any] = {}


def _handler(reply: dict[str, Any], status: int = 200):  # type: ignore[no-untyped-def]
    def handle(request: httpx.Request) -> httpx.Response:
        _CAPTURED["url"] = str(request.url)
        _CAPTURED["headers"] = dict(request.headers)
        _CAPTURED["body"] = json.loads(request.content or b"{}")
        return httpx.Response(status, json=reply)

    return handle


def _factory(handle):  # type: ignore[no-untyped-def]
    def make(_timeout: float) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(handle))

    return make


def _req() -> AssistantRequest:
    return AssistantRequest(
        task=AssistantTask.GENERATE,
        messages=[ChatMessage("system", "s"), ChatMessage("user", "u")],
        max_tokens=100,
        temperature=0.2,
    )


_OK_REPLY = {
    "model": "gpt-4o-mini",
    "choices": [{"message": {"content": "print(1)"}, "finish_reason": "stop"}],
    "usage": {"prompt_tokens": 10, "completion_tokens": 3},
}


async def test_openai_builds_request_and_parses() -> None:
    _CAPTURED.clear()
    p = OpenAIAssistantProvider(_factory(_handler(_OK_REPLY)))
    target = ResolvedAssistant(
        provider_id=None,  # type: ignore[arg-type]
        config={"model": "gpt-4o-mini"},
        secret="sk-test",
    )
    res = await p.complete(_req(), target, timeout_s=5)
    assert res.ok
    assert res.text == "print(1)"
    assert res.usage["prompt_tokens"] == 10
    assert _CAPTURED["url"].endswith("/v1/chat/completions")
    assert _CAPTURED["headers"]["authorization"] == "Bearer sk-test"
    assert _CAPTURED["body"]["model"] == "gpt-4o-mini"
    assert _CAPTURED["body"]["messages"][0] == {"role": "system", "content": "s"}


async def test_azure_url_and_header() -> None:
    _CAPTURED.clear()
    p = AzureOpenAIAssistantProvider(_factory(_handler(_OK_REPLY)))
    target = ResolvedAssistant(
        provider_id=None,  # type: ignore[arg-type]
        config={
            "endpoint": "https://x.openai.azure.com",
            "deployment": "gpt4o",
            "api_version": "2024-06-01",
        },
        secret="azkey",
    )
    res = await p.complete(_req(), target, timeout_s=5)
    assert res.ok
    assert "deployments/gpt4o/chat/completions" in _CAPTURED["url"]
    assert "api-version=2024-06-01" in _CAPTURED["url"]
    assert _CAPTURED["headers"]["api-key"] == "azkey"


async def test_ollama_no_secret_needed() -> None:
    _CAPTURED.clear()
    p = OllamaAssistantProvider(_factory(_handler(_OK_REPLY)))
    target = ResolvedAssistant(
        provider_id=None,  # type: ignore[arg-type]
        config={"base_url": "http://ollama:11434", "model": "llama3.1"},
        secret="",
    )
    res = await p.complete(_req(), target, timeout_s=5)
    assert res.ok
    assert _CAPTURED["url"] == "http://ollama:11434/v1/chat/completions"
    assert "authorization" not in _CAPTURED["headers"]


async def test_http_error_becomes_failure_not_raise() -> None:
    p = OpenAIAssistantProvider(_factory(_handler({"error": "nope"}, status=401)))
    target = ResolvedAssistant(
        provider_id=None,  # type: ignore[arg-type]
        config={"model": "gpt-4o-mini"},
        secret="bad",
    )
    res = await p.complete(_req(), target, timeout_s=5)
    assert res.ok is False
    assert "401" in (res.error or "")


async def test_transport_error_becomes_failure() -> None:
    def boom(_req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    p = OpenAIAssistantProvider(_factory(boom))
    target = ResolvedAssistant(
        provider_id=None,  # type: ignore[arg-type]
        config={"model": "m"},
        secret="k",
    )
    res = await p.complete(_req(), target, timeout_s=5)
    assert res.ok is False


@pytest.mark.parametrize(
    "provider,config,has_secret,ok",
    [
        (OpenAIAssistantProvider, {"model": "m"}, True, True),
        (OpenAIAssistantProvider, {"model": "m"}, False, False),
        (OpenAIAssistantProvider, {}, True, False),
        (AzureOpenAIAssistantProvider, {"endpoint": "e", "deployment": "d"}, True, True),
        (AzureOpenAIAssistantProvider, {"endpoint": "e"}, True, False),
        (OllamaAssistantProvider, {"base_url": "b", "model": "m"}, False, True),
        (OllamaAssistantProvider, {"base_url": "b"}, False, False),
    ],
)
def test_validate_config(
    provider: Any, config: dict[str, Any], has_secret: bool, ok: bool
) -> None:
    p = provider()
    if ok:
        p.validate_config(config, has_secret=has_secret)
    else:
        with pytest.raises(ConfigError):
            p.validate_config(config, has_secret=has_secret)


async def test_stream_parses_sse_deltas() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        chunks = [
            'data: {"choices":[{"delta":{"content":"pri"}}]}\n\n',
            'data: {"choices":[{"delta":{"content":"nt(1)"}}]}\n\n',
            "data: [DONE]\n\n",
        ]
        return httpx.Response(200, content="".join(chunks).encode())

    p = OpenAIAssistantProvider(_factory(handle))
    target = ResolvedAssistant(
        provider_id=None,  # type: ignore[arg-type]
        config={"model": "m"},
        secret="k",
    )
    out = [d async for d in p.stream(_req(), target, timeout_s=5)]
    assert "".join(out) == "print(1)"
