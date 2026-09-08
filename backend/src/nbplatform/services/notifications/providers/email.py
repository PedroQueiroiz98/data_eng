"""Sender de e-mail (spec §15). Toda a config vem de `configuration_json`."""

from __future__ import annotations

import asyncio
import html
import logging
from typing import Any

from nbplatform.domain.notifications import NotificationMessage, ProviderResult
from nbplatform.services.notifications.email_sender import (
    EmailProviderSettings,
    EmailSender,
    OutgoingEmail,
    SmtpEmailSender,
)
from nbplatform.services.notifications.providers.base import (
    ConfigError,
    NotificationSender,
    ResolvedTarget,
)

logger = logging.getLogger(__name__)


def _as_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [v.strip() for v in value.replace(";", ",").split(",") if v.strip()]
    return [str(v).strip() for v in value if str(v).strip()]


class EmailNotificationProvider(NotificationSender):
    provider_type = "EMAIL"

    def __init__(self, sender: EmailSender | None = None) -> None:
        self._sender = sender or SmtpEmailSender()

    # ── config ───────────────────────────────────────────────────────────
    def validate_config(self, config: dict[str, Any], *, has_secret: bool) -> None:
        if not str(config.get("host") or "").strip():
            raise ConfigError("SMTP host é obrigatório.")
        if not str(config.get("from_email") or "").strip():
            raise ConfigError("From Email é obrigatório.")
        port = config.get("port")
        if port is not None and not (isinstance(port, int) and 1 <= port <= 65535):
            raise ConfigError("SMTP port inválida.")
        if not _as_list(config.get("recipients")):
            raise ConfigError("Informe ao menos um destinatário.")

    def summary(self, config: dict[str, Any]) -> str:
        host = config.get("host") or "—"
        port = config.get("port") or 587
        n = len(_as_list(config.get("recipients")))
        return f"{host}:{port} · {n} destinatário(s)"

    def _settings(self, target: ResolvedTarget) -> EmailProviderSettings:
        c = target.config
        return EmailProviderSettings(
            host=str(c.get("host") or "").strip(),
            port=int(c.get("port") or 587),
            username=str(c.get("username") or "").strip(),
            password=target.secret,
            from_email=str(c.get("from_email") or "").strip(),
            from_name=str(c.get("from_name") or "").strip(),
            use_tls=bool(c.get("use_tls", True)),
        )

    def targets(self, target: ResolvedTarget) -> list[str]:
        return _as_list(target.config.get("recipients"))

    # ── envio ────────────────────────────────────────────────────────────
    async def send(
        self,
        message: NotificationMessage,
        target: ResolvedTarget,
        *,
        timeout_s: float,
    ) -> ProviderResult:
        recipients = _as_list(target.config.get("recipients"))
        if not recipients:
            return ProviderResult.failure("nenhum destinatário configurado")
        settings = self._settings(target)
        if not settings.usable:
            return ProviderResult.failure("configuração de e-mail incompleta")

        email = OutgoingEmail(
            subject=_subject(message),
            html_body=_html_body(message),
            text_body=_text_body(message),
            to=recipients,
            cc=_as_list(target.config.get("cc")),
            bcc=_as_list(target.config.get("bcc")),
        )
        try:
            await asyncio.wait_for(self._sender.send(email, settings), timeout=timeout_s)
        except TimeoutError:
            return ProviderResult.failure(f"timeout após {timeout_s:.0f}s")
        except Exception as exc:  # noqa: BLE001 - erro vira ProviderResult
            return ProviderResult.failure(f"{type(exc).__name__}: {exc}")
        return ProviderResult.success(f"{len(recipients)} destinatário(s)")


def _subject(m: NotificationMessage) -> str:
    tag = m.event_type.replace("_", " ")
    return f"[{tag}] {m.pipeline_name} - {m.job_name}"


def _text_body(m: NotificationMessage) -> str:
    rows = [
        ("Workflow", m.pipeline_name),
        ("Job", m.job_name),
        ("Execution", f"#{m.execution_id}"),
        ("Ambiente", m.environment),
        ("Erro", m.error_message or "—"),
        ("Componente", m.error_type or m.notebook_name or "—"),
        ("Data", m.timestamp.isoformat()),
        ("Attempt", str(m.attempt)),
        ("Correlation ID", m.correlation_id or "—"),
    ]
    lines = [m.message or "Falha na execução.", ""]
    lines += [f"{k}: {v}" for k, v in rows]
    if m.execution_url:
        lines += ["", f"Abrir execução: {m.execution_url}"]
    return "\n".join(lines)


def _html_body(m: NotificationMessage) -> str:
    def esc(v: str) -> str:
        return html.escape(str(v))

    rows = "".join(
        f"<tr><td style='padding:4px 12px 4px 0;color:#64748b'>{esc(k)}</td>"
        f"<td style='padding:4px 0'>{esc(v)}</td></tr>"
        for k, v in [
            ("Workflow", m.pipeline_name),
            ("Job", m.job_name),
            ("Execution", f"#{m.execution_id}"),
            ("Ambiente", m.environment),
            ("Componente", m.error_type or m.notebook_name or "—"),
            ("Data", m.timestamp.isoformat()),
            ("Attempt", str(m.attempt)),
            ("Correlation ID", m.correlation_id or "—"),
        ]
    )
    err = (
        f"<pre style='background:#fef2f2;color:#b91c1c;padding:12px;border-radius:6px;"
        f"white-space:pre-wrap'>{esc(m.error_message)}</pre>"
        if m.error_message
        else ""
    )
    btn = (
        f"<p><a href='{esc(m.execution_url)}' style='display:inline-block;"
        f"background:#4f46e5;color:#fff;padding:10px 16px;border-radius:6px;"
        f"text-decoration:none'>Abrir execução</a></p>"
        if m.execution_url
        else ""
    )
    return (
        f"<div style='font-family:system-ui,Arial,sans-serif;color:#0f172a'>"
        f"<h2 style='margin:0 0 4px'>{esc(m.title)}</h2>"
        f"<p style='margin:0 0 12px;color:#64748b'>{esc(m.pipeline_name)} — {esc(m.job_name)}</p>"
        f"{err}<table style='border-collapse:collapse;font-size:14px'>{rows}</table>{btn}</div>"
    )
