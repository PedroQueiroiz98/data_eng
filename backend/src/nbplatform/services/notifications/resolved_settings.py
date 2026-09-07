"""Configuração global efetiva dos providers = linha do banco + fallback de env.

Os secrets (senha SMTP, bot token) só existem aqui, decifrados, no momento do
envio. Nunca são serializados nem logados.
"""

from __future__ import annotations

from dataclasses import dataclass

from nbplatform.core.config import Settings
from nbplatform.core.crypto import SecretCipher
from nbplatform.models.notification import NotificationSettings


@dataclass(frozen=True)
class EmailProviderSettings:
    enabled: bool
    host: str
    port: int
    username: str
    password: str
    sender: str
    use_tls: bool

    @property
    def usable(self) -> bool:
        return self.enabled and bool(self.host and self.sender)


@dataclass(frozen=True)
class BitrixProviderSettings:
    enabled: bool
    url: str
    send_message_path: str
    bot_id: str
    bot_token: str

    @property
    def usable(self) -> bool:
        return self.enabled and bool(self.url and self.bot_id and self.bot_token)


@dataclass(frozen=True)
class ResolvedSettings:
    email: EmailProviderSettings
    bitrix: BitrixProviderSettings


def resolve(
    row: NotificationSettings | None, settings: Settings, cipher: SecretCipher
) -> ResolvedSettings:
    def dec(ct: str | None) -> str:
        if not ct:
            return ""
        try:
            return cipher.decrypt(ct)
        except ValueError:  # pragma: no cover - dado corrompido
            return ""

    email = EmailProviderSettings(
        enabled=(row.email_enabled if row else False) or bool(settings.notify_smtp_host),
        host=(row.smtp_host if row and row.smtp_host else settings.notify_smtp_host),
        port=(row.smtp_port if row and row.smtp_port else settings.notify_smtp_port),
        username=(
            row.smtp_username if row and row.smtp_username else settings.notify_smtp_username
        ),
        password=(dec(row.smtp_password_ct) if row else "") or settings.notify_smtp_password,
        sender=(row.smtp_from if row and row.smtp_from else settings.notify_smtp_from),
        use_tls=(row.smtp_use_tls if row else settings.notify_smtp_use_tls),
    )
    bitrix = BitrixProviderSettings(
        enabled=(row.bitrix_enabled if row else False) or bool(settings.notify_bitrix_url),
        url=(row.bitrix_url if row and row.bitrix_url else settings.notify_bitrix_url),
        send_message_path=(
            row.bitrix_send_message_path
            if row and row.bitrix_send_message_path
            else settings.notify_bitrix_send_message_path
        ),
        bot_id=(row.bitrix_bot_id if row and row.bitrix_bot_id else settings.notify_bitrix_bot_id),
        bot_token=(dec(row.bitrix_bot_token_ct) if row else "")
        or settings.notify_bitrix_bot_token,
    )
    return ResolvedSettings(email=email, bitrix=bitrix)
