"""Provider de e-mail (spec §7)."""

from __future__ import annotations

import html
import logging

from nbplatform.domain.notifications import (
    NotificationChannel,
    NotificationMessage,
    ProviderResult,
)
from nbplatform.models.notification import NotificationConfig
from nbplatform.services.notifications.email_sender import EmailSender, OutgoingEmail
from nbplatform.services.notifications.resolved_settings import ResolvedSettings

logger = logging.getLogger(__name__)


class EmailNotificationProvider:
    type = NotificationChannel.EMAIL.value

    def __init__(self, sender: EmailSender) -> None:
        self._sender = sender

    def targets(self, config: NotificationConfig) -> list[str]:
        return list(config.email_recipients or [])

    async def send(
        self,
        message: NotificationMessage,
        config: NotificationConfig,
        settings: ResolvedSettings,
    ) -> ProviderResult:
        recipients = list(config.email_recipients or [])
        if not recipients:
            return ProviderResult.failure("nenhum destinatário configurado")
        if not settings.email.usable:
            return ProviderResult.failure("configuração global de e-mail incompleta")

        subject = config.email_subject or _default_subject(message)
        email = OutgoingEmail(
            subject=subject,
            html_body=_html_body(message),
            text_body=_text_body(message),
            to=recipients,
            cc=list(config.email_cc or []),
            bcc=list(config.email_bcc or []),
        )
        try:
            await self._sender.send(email, settings.email)
        except Exception as exc:  # noqa: BLE001 - erro vira ProviderResult
            return ProviderResult.failure(f"{type(exc).__name__}: {exc}")
        return ProviderResult.success(f"{len(recipients)} destinatário(s)")


def _default_subject(m: NotificationMessage) -> str:
    return f"[JOB FAILED] {m.pipeline_name} - {m.job_name}"


def _text_body(m: NotificationMessage) -> str:
    rows = [
        ("Pipeline", m.pipeline_name),
        ("Job", m.job_name),
        ("Status", "FAILED"),
        ("Environment", m.environment),
        ("Started", m.timestamp.isoformat()),
        ("Duration", _dur(m.duration_ms)),
        ("Error", m.error_message or "—"),
        ("Notebook", m.notebook_name or "—"),
        ("Attempt", str(m.attempt)),
        ("Execution", m.execution_id),
    ]
    lines = ["Falha na execução do Job", ""]
    for k, v in rows:
        lines.append(f"{k}: {v}")
    if m.execution_url:
        lines += ["", f"View Execution: {m.execution_url}"]
    return "\n".join(lines)


def _html_body(m: NotificationMessage) -> str:
    def esc(v: str) -> str:
        return html.escape(v)

    rows = "".join(
        f"<tr><td style='padding:4px 12px 4px 0;color:#64748b'>{esc(k)}</td>"
        f"<td style='padding:4px 0'>{esc(str(v))}</td></tr>"
        for k, v in [
            ("Pipeline", m.pipeline_name),
            ("Job", m.job_name),
            ("Status", "FAILED"),
            ("Environment", m.environment),
            ("Started", m.timestamp.isoformat()),
            ("Duration", _dur(m.duration_ms)),
            ("Notebook", m.notebook_name or "—"),
            ("Attempt", str(m.attempt)),
            ("Execution ID", m.execution_id),
        ]
    )
    err = (
        f"<pre style='background:#fef2f2;color:#b91c1c;padding:12px;border-radius:6px;"
        f"white-space:pre-wrap'>{esc(m.error_message)}</pre>"
        if m.error_message
        else ""
    )
    btn_style = (
        "display:inline-block;background:#4f46e5;color:#fff;padding:10px 16px;"
        "border-radius:6px;text-decoration:none"
    )
    btn = (
        f"<p><a href='{esc(m.execution_url)}' style='{btn_style}'>View Execution</a></p>"
        if m.execution_url
        else ""
    )
    return (
        f"<div style='font-family:system-ui,Arial,sans-serif;color:#0f172a'>"
        f"<h2 style='margin:0 0 4px'>🚨 Falha na execução do Job</h2>"
        f"<p style='margin:0 0 12px;color:#64748b'>{esc(m.pipeline_name)} — {esc(m.job_name)}</p>"
        f"{err}<table style='border-collapse:collapse;font-size:14px'>{rows}</table>{btn}</div>"
    )


def _dur(ms: int | None) -> str:
    if ms is None:
        return "—"
    s = round(ms / 1000)
    return f"{s}s" if s < 60 else f"{s // 60}m {s % 60:02d}s"
