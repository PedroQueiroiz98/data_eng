from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from nbplatform.domain.notifications import (
    NotificationChannel,
    NotificationEvent,
    NotificationStatus,
)

MASK = "********"


# ─── config por Pipeline/Workflow ────────────────────────────────────────────
class NotificationConfigRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    workflow_id: uuid.UUID
    on_failure: bool
    on_success: bool
    on_retry: bool
    on_cancelled: bool
    on_started: bool
    email_enabled: bool
    email_recipients: list[str]
    email_cc: list[str]
    email_bcc: list[str]
    email_subject: str | None
    bitrix_enabled: bool
    bitrix_dialog_id: str | None


class NotificationConfigUpdate(BaseModel):
    on_failure: bool = True
    on_success: bool = False
    on_retry: bool = False
    on_cancelled: bool = False
    on_started: bool = False
    email_enabled: bool = False
    email_recipients: list[str] = Field(default_factory=list)
    email_cc: list[str] = Field(default_factory=list)
    email_bcc: list[str] = Field(default_factory=list)
    email_subject: str | None = Field(default=None, max_length=300)
    bitrix_enabled: bool = False
    bitrix_dialog_id: str | None = Field(default=None, max_length=120)


# ─── settings globais (secrets nunca voltam) ─────────────────────────────────
class NotificationSettingsRead(BaseModel):
    email_enabled: bool = False
    smtp_host: str | None = None
    smtp_port: int | None = None
    smtp_username: str | None = None
    smtp_from: str | None = None
    smtp_use_tls: bool = True
    smtp_password_masked: str = ""  # "********" se definido

    bitrix_enabled: bool = False
    bitrix_url: str | None = None
    bitrix_send_message_path: str | None = None
    bitrix_bot_id: str | None = None
    bitrix_bot_token_masked: str = ""  # "********" se definido

    # fallback: notifica falha de pipelines sem config própria
    default_on_failure: bool = False
    default_email_recipients: list[str] = Field(default_factory=list)
    default_bitrix_dialog_id: str | None = None


class NotificationSettingsUpdate(BaseModel):
    email_enabled: bool = False
    smtp_host: str | None = None
    smtp_port: int | None = Field(default=None, ge=1, le=65535)
    smtp_username: str | None = None
    smtp_from: str | None = None
    smtp_use_tls: bool = True
    # None/"" mantém; "********" mantém; qualquer outro valor grava novo secret
    smtp_password: str | None = None

    bitrix_enabled: bool = False
    bitrix_url: str | None = None
    bitrix_send_message_path: str | None = None
    bitrix_bot_id: str | None = None
    bitrix_bot_token: str | None = None

    default_on_failure: bool = False
    default_email_recipients: list[str] = Field(default_factory=list)
    default_bitrix_dialog_id: str | None = None


# ─── histórico ──────────────────────────────────────────────────────────────
class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_id: uuid.UUID
    execution_id: uuid.UUID | None
    channel: NotificationChannel
    event_type: NotificationEvent
    status: NotificationStatus
    recipient: str | None
    attempt: int
    max_attempts: int
    error_message: str | None
    created_at: datetime
    sent_at: datetime | None
    next_retry_at: datetime | None
