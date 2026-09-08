"""Sender Bitrix (spec §13/§14).

Toda a config vem de `configuration_json` (`url`, `send_message_path`, `bot_id`,
`dialog_id`) + o token em `secret`.
- **bot** (Bot ID + Token): `POST {url}/rest/imbot.v2.Chat.Message.send` com
  `{botId, botToken, dialogId, fields:{message, attach}}`.
- **webhook de chat** (sem Bot ID/Token): `POST {url}/rest/im.message.add` com
  `{DIALOG_ID, MESSAGE, ATTACH}` (auth já no path do webhook).
Sucesso = 2xx sem `error` no corpo. Request e response sempre logados
(`botToken` mascarado, segmento de webhook redigido).
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Callable
from typing import Any

import httpx

from nbplatform.domain.notifications import NotificationMessage, ProviderResult
from nbplatform.services.notifications.providers.base import (
    ConfigError,
    NotificationSender,
    ResolvedTarget,
)

logger = logging.getLogger(__name__)

_GRID_FIELDS = (
    "Ambiente",
    "Erro",
    "Componente",
    "Evento",
    "Data/Hora",
    "Event ID",
    "Correlation ID",
    "Workflow",
    "Job",
    "Execution ID",
    "Attempt",
    "Duration",
)

ClientFactory = Callable[[float], httpx.AsyncClient]


def _default_client(timeout: float) -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=timeout)


class BitrixNotificationProvider(NotificationSender):
    provider_type = "BITRIX"

    def __init__(self, client_factory: ClientFactory | None = None) -> None:
        self._client_factory = client_factory or _default_client

    # ── config ───────────────────────────────────────────────────────────
    def validate_config(self, config: dict[str, Any], *, has_secret: bool) -> None:
        if not str(config.get("url") or "").strip():
            raise ConfigError("URL do Bitrix é obrigatória.")
        if not str(config.get("dialog_id") or "").strip():
            raise ConfigError("Dialog ID é obrigatório.")

    def summary(self, config: dict[str, Any]) -> str:
        return f"canal {config.get('dialog_id') or '—'}"

    def targets(self, target: ResolvedTarget) -> list[str]:
        dialog = str(target.config.get("dialog_id") or "").strip()
        return [dialog] if dialog else []

    # ── envio ────────────────────────────────────────────────────────────
    async def send(
        self,
        message: NotificationMessage,
        target: ResolvedTarget,
        *,
        timeout_s: float,
    ) -> ProviderResult:
        c = target.config
        url = str(c.get("url") or "").strip()
        dialog_id = str(c.get("dialog_id") or "").strip()
        bot_id = str(c.get("bot_id") or "").strip()
        token = target.secret
        path = str(c.get("send_message_path") or "").strip()
        if not url:
            return ProviderResult.failure("URL do Bitrix não configurada")
        if not dialog_id:
            return ProviderResult.failure("dialog_id não configurado")

        bot_mode = bool(bot_id and token)
        text = _message_text(message)
        attach = _attach(message)

        if bot_mode:
            endpoint = _endpoint(url, path, "imbot.v2.Chat.Message.send")
            payload: dict[str, Any] = {
                "botId": bot_id,
                "botToken": token,
                "dialogId": dialog_id,
                "fields": {"message": text, "attach": attach},
            }
        else:
            endpoint = _endpoint(url, path, "im.message.add")
            payload = {"DIALOG_ID": dialog_id, "MESSAGE": text, "ATTACH": attach}

        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        mode = "bot" if bot_mode else "webhook"
        logger.info(
            "Bitrix request",
            extra={
                "endpoint": _redact(endpoint),
                "mode": mode,
                "dialog_id": dialog_id,
                "request": _redact_payload(payload),
            },
        )

        started = time.perf_counter()
        try:
            async with self._client_factory(timeout_s) as client:
                resp = await asyncio.wait_for(
                    client.post(
                        endpoint,
                        content=json.dumps(payload).encode("utf-8"),
                        headers=headers,
                    ),
                    timeout=timeout_s,
                )
        except (TimeoutError, httpx.HTTPError) as exc:
            logger.warning(
                "Bitrix transport error",
                extra={
                    "endpoint": _redact(endpoint),
                    "mode": mode,
                    "dialog_id": dialog_id,
                    "error": f"{type(exc).__name__}: {exc}",
                },
            )
            return ProviderResult.failure(f"{type(exc).__name__}: {exc}")

        took_ms = round((time.perf_counter() - started) * 1000)
        body = (resp.text or "").strip()
        data = _safe_json(resp)
        api_error = (
            str(data.get("error_description") or data.get("error"))
            if isinstance(data, dict) and data.get("error")
            else None
        )
        log_extra = {
            "status": resp.status_code,
            "endpoint": _redact(endpoint),
            "mode": mode,
            "dialog_id": dialog_id,
            "duration_ms": took_ms,
            "response": body[:1000],
        }
        if not resp.is_success or api_error:
            detail = api_error or body[:500] or f"HTTP {resp.status_code}"
            logger.warning("Bitrix response (falha)", extra=log_extra)
            return ProviderResult.failure(f"HTTP {resp.status_code}: {detail}")

        logger.info("Bitrix response (ok)", extra=log_extra)
        return ProviderResult.success(f"dialog {dialog_id}")


def _endpoint(url: str, path: str, default_method: str) -> str:
    """Junta base + recurso tolerando barra faltando/sobrando."""
    path = (path or "").strip()
    if path.startswith(("http://", "https://")):
        return path
    base = url.rstrip("/")
    if not path:
        return f"{base}/rest/{default_method}"
    if not path.startswith("/"):
        path = "/" + path
    return base + path


def _redact(endpoint: str) -> str:
    parts = endpoint.split("/rest/", 1)
    return parts[0] + "/rest/***" if len(parts) == 2 else endpoint


def _redact_payload(payload: dict[str, Any]) -> dict[str, Any]:
    out = dict(payload)
    if "botToken" in out:
        out["botToken"] = "***"
    return out


def _message_text(m: NotificationMessage) -> str:
    lines = [
        f"[B]{m.title}[/B]",
        "",
        f"Workflow: {m.pipeline_name}",
        f"Job: {m.job_name}",
        f"Execution: #{m.execution_id}",
    ]
    if m.error_message:
        lines += ["", "💥 Erro:", m.error_message]
    lines += ["", "Ambiente:", m.environment]
    if m.execution_url:
        lines += ["", f"[URL={m.execution_url}]Abrir execução[/URL]"]
    return "\n".join(lines)


def _attach(m: NotificationMessage) -> list[dict[str, Any]]:
    grid = [
        {"NAME": name, "VALUE": str(m.metadata.get(name, "—")), "DISPLAY": "LINE"}
        for name in _GRID_FIELDS
    ]
    return [
        {"DELIMITER": {"SIZE": 600, "COLOR": "#e01e5a"}},
        {"GRID": grid},
    ]


def _safe_json(resp: httpx.Response) -> object:
    try:
        return resp.json()
    except ValueError:
        return None
