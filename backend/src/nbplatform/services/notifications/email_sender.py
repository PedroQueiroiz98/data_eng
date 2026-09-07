"""Abstração de envio de e-mail (a aplicação não tinha uma).

`SmtpEmailSender` usa a stdlib (`smtplib`) num thread para não bloquear o loop.
Trocar por SES/SendGrid/etc. é só implementar `EmailSender`.
"""

from __future__ import annotations

import asyncio
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Protocol

from nbplatform.services.notifications.resolved_settings import EmailProviderSettings


@dataclass(frozen=True)
class OutgoingEmail:
    subject: str
    html_body: str
    text_body: str
    to: list[str]
    cc: list[str]
    bcc: list[str]


class EmailSender(Protocol):
    async def send(self, email: OutgoingEmail, settings: EmailProviderSettings) -> None:
        """Envia ou levanta exceção (o provider trata retry/histórico)."""
        ...


class SmtpEmailSender:
    async def send(self, email: OutgoingEmail, settings: EmailProviderSettings) -> None:
        recipients = [*email.to, *email.cc, *email.bcc]
        if not recipients:
            raise ValueError("nenhum destinatário configurado")
        await asyncio.to_thread(self._send_sync, email, settings, recipients)

    @staticmethod
    def _send_sync(
        email: OutgoingEmail, settings: EmailProviderSettings, recipients: list[str]
    ) -> None:
        msg = EmailMessage()
        msg["Subject"] = email.subject
        msg["From"] = settings.sender
        msg["To"] = ", ".join(email.to)
        if email.cc:
            msg["Cc"] = ", ".join(email.cc)
        msg.set_content(email.text_body)
        msg.add_alternative(email.html_body, subtype="html")

        with smtplib.SMTP(settings.host, settings.port, timeout=20) as smtp:
            if settings.use_tls:
                smtp.starttls(context=ssl.create_default_context())
            if settings.username and settings.password:
                smtp.login(settings.username, settings.password)
            smtp.send_message(msg, from_addr=settings.sender, to_addrs=recipients)
