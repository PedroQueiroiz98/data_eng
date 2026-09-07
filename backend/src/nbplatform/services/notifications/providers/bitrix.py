"""Provider Bitrix (spec §5/§6).

Não havia integração Bitrix — este é um client mínimo. O envio faz
`POST {url}{send_message_path}` com `{botId, botToken, dialogId, fields}` e usa o
mecanismo de `attach` (DELIMITER + GRID) para a ficha do incidente.
"""

from __future__ import annotations

import logging
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


class BitrixNotificationProvider:
    type = NotificationChannel.BITRIX.value

    def targets(self, config: NotificationConfig) -> list[str]:
        return [config.bitrix_dialog_id] if config.bitrix_dialog_id else []

    async def send(
        self,
        message: NotificationMessage,
        config: NotificationConfig,
        settings: ResolvedSettings,
    ) -> ProviderResult:
        dialog_id = config.bitrix_dialog_id
        if not dialog_id:
            return ProviderResult.failure("dialog_id não configurado")
        if not settings.bitrix.usable:
            return ProviderResult.failure("configuração global do Bitrix incompleta")

        b = settings.bitrix
        url = b.url.rstrip("/") + b.send_message_path
        payload: dict[str, Any] = {
            "botId": b.bot_id,
            "botToken": b.bot_token,
            "dialogId": dialog_id,
            "fields": {
                "message": _message_text(message),
                "attach": _attach(message),
            },
        }
        timeout = get_settings().notification_send_timeout_s
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(url, json=payload)
            if resp.status_code >= 400:
                return ProviderResult.failure(f"HTTP {resp.status_code}: {resp.text[:200]}")
            data = _safe_json(resp)
            if isinstance(data, dict) and data.get("error"):
                return ProviderResult.failure(
                    str(data.get("error_description") or data.get("error"))
                )
        except httpx.HTTPError as exc:
            return ProviderResult.failure(f"{type(exc).__name__}: {exc}")
        return ProviderResult.success(f"dialog {dialog_id}")


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
        {"NAME": name, "VALUE": m.metadata.get(name, "—"), "DISPLAY": "LINE"}
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
