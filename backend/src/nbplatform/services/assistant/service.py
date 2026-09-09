"""AssistantService: resolve o provider ativo, monta contexto, chama e audita.

- nunca ramifica por tipo de provider (usa o `AssistantProviderRegistry`);
- `run`/`inline_complete` NUNCA levantam — degradam para `ok=False` / "";
- o prompt/contexto NUNCA é persistido; só métricas e (opcionalmente) o texto.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import replace
from typing import Any

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from nbplatform.core.config import get_settings
from nbplatform.core.crypto import SecretCipher
from nbplatform.domain.assistant import (
    AssistantRequest,
    AssistantResult,
    AssistantTask,
    ChatMessage,
)
from nbplatform.repositories.assistant_repository import AssistantRepository
from nbplatform.services.assistant import context as ctx_builder
from nbplatform.services.assistant import prompts
from nbplatform.services.assistant.interface import IAssistantService
from nbplatform.services.assistant.providers import ResolvedAssistant
from nbplatform.services.assistant.providers.base import AssistantProvider
from nbplatform.services.assistant.registry import (
    AssistantProviderRegistry,
    UnknownProviderType,
    default_registry,
)


class AssistantService(IAssistantService):
    def __init__(
        self,
        session: AsyncSession,
        redis: Redis | None = None,
        *,
        registry: AssistantProviderRegistry | None = None,
    ) -> None:
        self.session = session
        self.redis = redis
        self.settings = get_settings()
        self._registry = registry or default_registry()
        self._cipher = SecretCipher(self.settings.secret_encryption_key)

    # ── resolução do provider ────────────────────────────────────────────
    async def _resolve(
        self,
    ) -> tuple[AssistantProvider, ResolvedAssistant, str] | None:
        repo = AssistantRepository(self.session)
        row = await repo.default_provider()
        if row is None or not self._registry.has(row.provider_type):
            return None
        provider = self._registry.get(row.provider_type)
        secret = ""
        if row.secret_ct:
            try:
                secret = self._cipher.decrypt(row.secret_ct)
            except ValueError:
                secret = ""
        target = ResolvedAssistant(
            provider_id=row.id, config=dict(row.configuration_json or {}), secret=secret
        )
        return provider, target, row.provider_type

    async def _rate_limited(self, user_id: uuid.UUID | None) -> bool:
        if self.redis is None or user_id is None:
            return False
        key = f"nbp:assistant:rl:{user_id}:{int(time.time() // 60)}"
        try:
            n = await self.redis.incr(key)
            if n == 1:
                await self.redis.expire(key, 65)
        except Exception:  # noqa: BLE001
            return False
        return int(n) > self.settings.assistant_rate_limit_per_min

    async def _build_context(self, task: AssistantTask, kw: dict[str, Any]) -> Any:
        return await ctx_builder.build_context(
            self.session,
            cells=list(kw.get("cells") or []),
            active_index=int(kw.get("active_cell_index") or 0),
            cursor_line=kw.get("cursor_line"),
            cursor_col=kw.get("cursor_column"),
            task=task,
            recent_error=kw.get("recent_error"),
            workspace_files=kw.get("workspace_files"),
            selection=kw.get("selection"),
            user_id=kw.get("user_id"),
        )

    def _messages(self, task: AssistantTask, ctx: Any, kw: dict[str, Any]) -> list[ChatMessage]:
        history_raw = kw.get("chat_history") or []
        history = [
            ChatMessage(role=m["role"], content=m["content"])
            if isinstance(m, dict)
            else m
            for m in history_raw
        ]
        return prompts.build_messages(
            task,
            ctx,
            instruction=kw.get("instruction"),
            chat_history=history,
            target_language=kw.get("target_language"),
        )

    async def _record(
        self,
        *,
        task: AssistantTask,
        provider_type: str | None,
        provider_id: uuid.UUID | None,
        user_id: uuid.UUID | None,
        notebook_path: str | None,
        cell_id: str | None,
        prompt_chars: int,
        result: AssistantResult,
        duration_ms: int,
    ) -> uuid.UUID | None:
        try:
            return await AssistantRepository(self.session).create_interaction(
                user_id=user_id,
                provider_id=provider_id,
                provider_type=provider_type,
                task=task,
                notebook_path=notebook_path,
                cell_id=cell_id,
                model=result.model or None,
                prompt_chars=prompt_chars,
                completion_chars=len(result.text),
                prompt_tokens=result.usage.get("prompt_tokens") or None,
                completion_tokens=result.usage.get("completion_tokens") or None,
                duration_ms=duration_ms,
                ok=result.ok,
                error=result.error,
                result_text=result.text
                if (self.settings.assistant_store_result_text and result.ok)
                else None,
            )
        except Exception:  # noqa: BLE001 - histórico nunca derruba a resposta
            return None

    # ── API pública ─────────────────────────────────────────────────────
    async def run(self, task: AssistantTask, **kwargs: Any) -> AssistantResult:
        if not self.settings.assistant_enabled:
            return AssistantResult.failure("assistente de IA desativado")
        user_id = kwargs.get("user_id")
        if await self._rate_limited(user_id):
            return AssistantResult.failure("limite de requisições por minuto atingido")
        resolved = await self._resolve()
        if resolved is None:
            return AssistantResult.failure("no provider configured")
        provider, target, ptype = resolved
        try:
            ctx = await self._build_context(task, kwargs)
            messages = self._messages(task, ctx, kwargs)
            req = AssistantRequest(
                task=task,
                messages=messages,
                max_tokens=self.settings.assistant_max_output_tokens,
                temperature=float(target.config.get("temperature", 0.2)),
            )
            prompt_chars = sum(len(m.content) for m in messages)
            started = time.perf_counter()
            result = await provider.complete(
                req, target, timeout_s=self.settings.assistant_request_timeout_s
            )
        except Exception as exc:  # noqa: BLE001 - provider nunca deveria levantar
            result = AssistantResult.failure(f"{type(exc).__name__}: {exc}")
            prompt_chars = 0
            started = time.perf_counter()
        duration_ms = int((time.perf_counter() - started) * 1000)
        interaction_id = await self._record(
            task=task,
            provider_type=ptype,
            provider_id=target.provider_id,
            user_id=user_id,
            notebook_path=kwargs.get("notebook_path"),
            cell_id=kwargs.get("cell_id"),
            prompt_chars=prompt_chars,
            result=result,
            duration_ms=duration_ms,
        )
        return replace(
            result, interaction_id=str(interaction_id) if interaction_id else None
        )

    async def stream(
        self, task: AssistantTask, **kwargs: Any
    ) -> AsyncIterator[dict[str, Any]]:
        if not self.settings.assistant_enabled:
            yield {"done": True, "error": "assistente de IA desativado"}
            return
        resolved = await self._resolve()
        if resolved is None:
            yield {"done": True, "error": "no provider configured"}
            return
        provider, target, ptype = resolved
        ctx = await self._build_context(task, kwargs)
        messages = self._messages(task, ctx, kwargs)
        req = AssistantRequest(
            task=task,
            messages=messages,
            max_tokens=self.settings.assistant_max_output_tokens,
            temperature=float(target.config.get("temperature", 0.2)),
            stream=True,
        )
        prompt_chars = sum(len(m.content) for m in messages)
        started = time.perf_counter()
        buf: list[str] = []
        error: str | None = None
        try:
            async for delta in provider.stream(
                req, target, timeout_s=self.settings.assistant_request_timeout_s
            ):
                buf.append(delta)
                yield {"delta": delta}
        except Exception as exc:  # noqa: BLE001
            error = f"{type(exc).__name__}: {exc}"
        text = "".join(buf)
        result = (
            AssistantResult.failure(error)
            if error
            else AssistantResult.success(text, model=str(target.config.get("model") or ""))
        )
        interaction_id = await self._record(
            task=task,
            provider_type=ptype,
            provider_id=target.provider_id,
            user_id=kwargs.get("user_id"),
            notebook_path=kwargs.get("notebook_path"),
            cell_id=kwargs.get("cell_id"),
            prompt_chars=prompt_chars,
            result=result,
            duration_ms=int((time.perf_counter() - started) * 1000),
        )
        yield {
            "done": True,
            "error": error,
            "interaction_id": str(interaction_id) if interaction_id else None,
        }

    async def inline_complete(self, **kwargs: Any) -> str:
        if not self.settings.assistant_enabled:
            return ""
        resolved = await self._resolve()
        if resolved is None:
            return ""
        provider, target, _ = resolved
        if not target.config.get("inline", True):
            return ""
        try:
            ctx = await self._build_context(AssistantTask.INLINE, kwargs)
            messages = self._messages(AssistantTask.INLINE, ctx, kwargs)
            req = AssistantRequest(
                task=AssistantTask.INLINE,
                messages=messages,
                max_tokens=self.settings.assistant_inline_max_tokens,
                temperature=0.1,
                stop=["\n\n"],
            )
            result = await provider.complete(
                req, target, timeout_s=self.settings.assistant_inline_timeout_s
            )
        except Exception:  # noqa: BLE001
            return ""
        if not result.ok:
            return ""
        text = result.text.strip("`")
        if text.startswith("python\n"):
            text = text[len("python\n") :]
        return text

    async def availability(self) -> dict[str, Any]:
        resolved = await self._resolve()
        if resolved is None:
            return {
                "configured": False,
                "provider_type": None,
                "inline_enabled": False,
                "models": [],
            }
        _provider, target, ptype = resolved
        model = str(target.config.get("model") or target.config.get("deployment") or "")
        return {
            "configured": True,
            "provider_type": ptype,
            "inline_enabled": self.settings.assistant_enabled
            and bool(target.config.get("inline", True)),
            "models": [model] if model else [],
        }


__all__ = ["AssistantService", "UnknownProviderType"]
