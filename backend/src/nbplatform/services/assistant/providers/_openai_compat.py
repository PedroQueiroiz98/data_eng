"""Base para providers que falam o protocolo OpenAI `chat/completions`.

OpenAI, Azure OpenAI e Ollama (endpoint `/v1`) usam o mesmo formato de request e
de streaming SSE. As subclasses só fornecem endpoint, headers e model.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Callable
from typing import Any

import httpx

from nbplatform.core.config import get_settings
from nbplatform.domain.assistant import AssistantRequest, AssistantResult

ClientFactory = Callable[[float], httpx.AsyncClient]


def _default_client(timeout: float) -> httpx.AsyncClient:
    settings = get_settings()
    return httpx.AsyncClient(
        timeout=httpx.Timeout(timeout, connect=settings.assistant_http_connect_timeout_s)
    )


class OpenAICompatBase:
    provider_type: str = "OPENAI_COMPAT"

    def __init__(self, client_factory: ClientFactory | None = None) -> None:
        self._client_factory = client_factory or _default_client

    # ── hooks das subclasses ─────────────────────────────────────────────
    def _endpoint(self, config: dict[str, Any]) -> str:
        raise NotImplementedError

    def _headers(self, config: dict[str, Any], secret: str) -> dict[str, str]:
        raise NotImplementedError

    def _model(self, config: dict[str, Any]) -> str:
        return str(config.get("model") or "")

    # ── payload ──────────────────────────────────────────────────────────
    def _payload(self, request: AssistantRequest, config: dict[str, Any]) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": self._model(config),
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
        }
        if request.stop:
            body["stop"] = request.stop
        return body

    # ── chamadas ─────────────────────────────────────────────────────────
    async def complete(
        self,
        request: AssistantRequest,
        target: Any,
        *,
        timeout_s: float,
    ) -> AssistantResult:
        body = self._payload(request, target.config)
        try:
            async with self._client_factory(timeout_s) as client:
                resp = await client.post(
                    self._endpoint(target.config),
                    json=body,
                    headers=self._headers(target.config, target.secret),
                )
        except (httpx.HTTPError, TimeoutError) as exc:
            return AssistantResult.failure(f"{type(exc).__name__}: {exc}")

        if resp.status_code >= 400:
            return AssistantResult.failure(
                f"HTTP {resp.status_code}: {(resp.text or '')[:400]}"
            )
        try:
            data = resp.json()
        except ValueError:
            return AssistantResult.failure("resposta não-JSON do provider")
        try:
            choice = data["choices"][0]
            text = choice["message"]["content"] or ""
            finish = str(choice.get("finish_reason") or "")
        except (KeyError, IndexError, TypeError):
            return AssistantResult.failure("formato de resposta inesperado")
        usage_raw = data.get("usage") or {}
        usage = {
            "prompt_tokens": int(usage_raw.get("prompt_tokens", 0) or 0),
            "completion_tokens": int(usage_raw.get("completion_tokens", 0) or 0),
        }
        return AssistantResult.success(
            text,
            model=str(data.get("model") or self._model(target.config)),
            finish_reason=finish,
            usage=usage,
        )

    def supports_stream(self) -> bool:
        return True

    async def stream(
        self,
        request: AssistantRequest,
        target: Any,
        *,
        timeout_s: float,
    ) -> AsyncIterator[str]:
        body = self._payload(request, target.config)
        body["stream"] = True
        try:
            async with (
                self._client_factory(timeout_s) as client,
                client.stream(
                    "POST",
                    self._endpoint(target.config),
                    json=body,
                    headers=self._headers(target.config, target.secret),
                ) as resp,
            ):
                if resp.status_code >= 400:
                    raw = (await resp.aread()).decode(errors="replace")
                    raise RuntimeError(f"HTTP {resp.status_code}: {raw[:400]}")
                async for line in resp.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    chunk = line[len("data:") :].strip()
                    if not chunk or chunk == "[DONE]":
                        continue
                    try:
                        piece = json.loads(chunk)
                        delta = piece["choices"][0]["delta"].get("content")
                    except (ValueError, KeyError, IndexError, TypeError):
                        continue
                    if delta:
                        yield delta
        except (httpx.HTTPError, TimeoutError) as exc:
            raise RuntimeError(f"{type(exc).__name__}: {exc}") from exc
