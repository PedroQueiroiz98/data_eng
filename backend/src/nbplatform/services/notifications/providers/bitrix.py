"""Provider Bitrix (spec §5/§6).

Porta o `BitrixService` de referência.
- **bot** (BitrixBotConfig / InvitaBot): `POST {Url}/rest/imbot.v2.Chat.Message.send`
  com `{botId, botToken, dialogId, fields:{message, attach}}`.
- **webhook de chat** (sem Bot ID/Token): `POST {Url}/rest/im.message.add` com
  `{DIALOG_ID, MESSAGE, ATTACH}`.
JSON UTF-8, `Accept: application/json`. Sucesso = 2xx sem `error` no corpo.
Falha → `ProviderResult` com o corpo real da resposta; request e response são
sempre logados (`botToken` mascarado).
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from typing import Any

import httpx

from nbplatform.core.config import get_settings
from nbplatform.domain.notifications import (
    NotificationChannel,
    NotificationMessage,
    ProviderResult,
)
from nbplatform.models.notification import NotificationConfig
from nbplatform.services.notifications.resolved_settings import ResolvedSettings

logger = logging.getLogger(__name__)

_GRID_FIELDS = (
    "Ambiente",
    "Erro",
    "Componente",
    "Evento",
    "Data/Hora",
    "Event ID",
    "Correlation ID",
    "Pipeline",
    "Job",
    "Execution ID",
    "Attempt",
    "Duration",
)


ClientFactory = Callable[[float], httpx.AsyncClient]


def _default_client(timeout: float) -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=timeout)


class BitrixNotificationProvider:
    type = NotificationChannel.BITRIX.value

    def __init__(self, client_factory: ClientFactory | None = None) -> None:
        self._client_factory = client_factory or _default_client

    def targets(self, config: NotificationConfig) -> list[str]:
        return [config.bitrix_dialog_id] if config.bitrix_dialog_id else []

    async def send(
        self,
        message: NotificationMessage,
        config: NotificationConfig,
        settings: ResolvedSettings,
    ) -> ProviderResult:
        dialog_id = (config.bitrix_dialog_id or "").strip()
        if not dialog_id:
            return ProviderResult.failure("dialog_id não configurado")
        if not settings.bitrix.usable:
            return ProviderResult.failure("configuração global do Bitrix incompleta")

        b = settings.bitrix
        text = _message_text(message)
        attach = _attach(message)

        if b.bot_mode:
            # fluxo de bot (referência BitrixBotConfig): imbot.v2.Chat.Message.send
            endpoint = _endpoint(b.url, b.send_message_path, "imbot.v2.Chat.Message.send")
            payload: dict[str, Any] = {
                "botId": b.bot_id,
                "botToken": b.bot_token,
                "dialogId": dialog_id,
                "fields": {"message": text, "attach": attach},
            }
        else:
            # webhook de chat: im.message.add (auth já vai no path do webhook)
            endpoint = _endpoint(b.url, b.send_message_path, "im.message.add")
            payload = {"DIALOG_ID": dialog_id, "MESSAGE": text, "ATTACH": attach}

        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        timeout = get_settings().notification_send_timeout_s
        mode = "bot" if b.bot_mode else "webhook"

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
            async with self._client_factory(timeout) as client:
                resp = await client.post(
                    endpoint,
                    content=json.dumps(payload).encode("utf-8"),
                    headers=headers,
                )
        except httpx.HTTPError as exc:
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

        # loga SEMPRE o retorno do Bitrix (status + corpo)
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
    """Esconde o segmento de webhook (`/rest/<id>/<code>/`) nos logs."""
    parts = endpoint.split("/rest/", 1)
    return parts[0] + "/rest/***" if len(parts) == 2 else endpoint


def _redact_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Copia o payload mascarando o `botToken` para o log da requisição."""
    out = dict(payload)
    if "botToken" in out:
        out["botToken"] = "***"
    return out


def _message_text(m: NotificationMessage) -> str:
    lines = [
        f"[B]{m.title}[/B]",
        "",
        f"Pipeline: {m.pipeline_name}",
        f"Job: {m.job_name}",
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
