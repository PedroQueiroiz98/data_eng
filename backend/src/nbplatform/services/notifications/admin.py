"""CRUD das configurações de notificação (por pipeline e global).

Regras de secret: o valor cru nunca sai; ao gravar, `None`/""/"********" mantêm o
valor atual, qualquer outro texto grava um novo secret cifrado.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from nbplatform.core.config import get_settings
from nbplatform.core.crypto import SecretCipher
from nbplatform.core.errors import NotFoundError
from nbplatform.models.workflow import Workflow
from nbplatform.repositories.notification_repository import NotificationRepository
from nbplatform.schemas.notification import (
    MASK,
    NotificationConfigRead,
    NotificationConfigUpdate,
    NotificationSettingsRead,
    NotificationSettingsUpdate,
)


def _cipher() -> SecretCipher:
    return SecretCipher(get_settings().secret_encryption_key)


def _keep_secret(new: str | None) -> bool:
    return new is None or new == "" or new == MASK


async def get_config(session: AsyncSession, workflow_id: uuid.UUID) -> NotificationConfigRead:
    if await session.get(Workflow, workflow_id) is None:
        raise NotFoundError(f"Workflow {workflow_id} não encontrado.")
    repo = NotificationRepository(session)
    cfg = await repo.get_config(workflow_id)
    if cfg is None:
        cfg = await repo.upsert_config(workflow_id)
    return NotificationConfigRead.model_validate(cfg)


async def put_config(
    session: AsyncSession, workflow_id: uuid.UUID, payload: NotificationConfigUpdate
) -> NotificationConfigRead:
    if await session.get(Workflow, workflow_id) is None:
        raise NotFoundError(f"Workflow {workflow_id} não encontrado.")
    cfg = await NotificationRepository(session).upsert_config(workflow_id)
    cfg.on_failure = payload.on_failure
    cfg.on_success = payload.on_success
    cfg.on_retry = payload.on_retry
    cfg.on_cancelled = payload.on_cancelled
    cfg.on_started = payload.on_started
    cfg.email_enabled = payload.email_enabled
    cfg.email_recipients = [e.strip() for e in payload.email_recipients if e.strip()]
    cfg.email_cc = [e.strip() for e in payload.email_cc if e.strip()]
    cfg.email_bcc = [e.strip() for e in payload.email_bcc if e.strip()]
    cfg.email_subject = payload.email_subject or None
    cfg.bitrix_enabled = payload.bitrix_enabled
    cfg.bitrix_dialog_id = (payload.bitrix_dialog_id or "").strip() or None
    await session.flush()
    return NotificationConfigRead.model_validate(cfg)


async def get_settings_read(session: AsyncSession) -> NotificationSettingsRead:
    """Config efetiva para exibir: linha do banco + fallback de env (sem secrets)."""
    row = await NotificationRepository(session).get_settings_row()
    s = get_settings()

    def pick(db_val: object, env_val: object) -> object:
        return db_val if db_val not in (None, "") else (env_val or None)

    return NotificationSettingsRead(
        email_enabled=(row.email_enabled if row else False) or bool(s.notify_smtp_host),
        smtp_host=pick(row.smtp_host if row else None, s.notify_smtp_host),
        smtp_port=pick(row.smtp_port if row else None, s.notify_smtp_port),
        smtp_username=pick(row.smtp_username if row else None, s.notify_smtp_username),
        smtp_from=pick(row.smtp_from if row else None, s.notify_smtp_from),
        smtp_use_tls=(row.smtp_use_tls if row else s.notify_smtp_use_tls),
        smtp_password_masked=MASK
        if (row and row.smtp_password_ct) or s.notify_smtp_password
        else "",
        bitrix_enabled=(row.bitrix_enabled if row else False) or bool(s.notify_bitrix_url),
        bitrix_url=pick(row.bitrix_url if row else None, s.notify_bitrix_url),
        bitrix_send_message_path=pick(
            row.bitrix_send_message_path if row else None, s.notify_bitrix_send_message_path
        ),
        bitrix_bot_id=pick(row.bitrix_bot_id if row else None, s.notify_bitrix_bot_id),
        bitrix_bot_token_masked=MASK
        if (row and row.bitrix_bot_token_ct) or s.notify_bitrix_bot_token
        else "",
    )


async def put_settings(
    session: AsyncSession, payload: NotificationSettingsUpdate
) -> NotificationSettingsRead:
    row = await NotificationRepository(session).upsert_settings_row()
    cipher = _cipher()

    row.email_enabled = payload.email_enabled
    row.smtp_host = payload.smtp_host or None
    row.smtp_port = payload.smtp_port
    row.smtp_username = payload.smtp_username or None
    row.smtp_from = payload.smtp_from or None
    row.smtp_use_tls = payload.smtp_use_tls
    if not _keep_secret(payload.smtp_password):
        row.smtp_password_ct = cipher.encrypt(payload.smtp_password or "")

    row.bitrix_enabled = payload.bitrix_enabled
    row.bitrix_url = payload.bitrix_url or None
    row.bitrix_send_message_path = payload.bitrix_send_message_path or None
    row.bitrix_bot_id = payload.bitrix_bot_id or None
    if not _keep_secret(payload.bitrix_bot_token):
        row.bitrix_bot_token_ct = cipher.encrypt(payload.bitrix_bot_token or "")

    await session.flush()
    return await get_settings_read(session)
