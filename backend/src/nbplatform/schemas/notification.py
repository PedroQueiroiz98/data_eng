from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from nbplatform.domain.notifications import (
    NotificationEventType,
    NotificationProviderType,
    NotificationStatus,
)

MASK = "********"


# ─── providers ──────────────────────────────────────────────────────────────
class NotificationProviderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    provider_type: NotificationProviderType
    enabled: bool
    configuration: dict[str, Any]  # = configuration_json, sem secrets
    has_password: bool
    has_credential: bool
    summary: str
    created_at: datetime
    updated_at: datetime


class NotificationProviderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    provider_type: NotificationProviderType
    enabled: bool = False
    configuration: dict[str, Any] = Field(default_factory=dict)
    # write-only: senha SMTP / token Bitrix
    secret: str | None = None


class NotificationProviderUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    enabled: bool | None = None
    configuration: dict[str, Any] | None = None
    # None / "" / "********" mantém; qualquer outro valor grava novo secret
    secret: str | None = None


class NotificationProviderEnabledPatch(BaseModel):
    enabled: bool


class NotificationTestResult(BaseModel):
    ok: bool
    detail: str = ""
    error: str | None = None


# ─── deliveries (histórico) ────────────────────────────────────────────────
class NotificationDeliveryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    notification_provider_id: uuid.UUID | None
    provider_type: NotificationProviderType
    event_type: NotificationEventType
    workflow_id: uuid.UUID | None
    job_id: uuid.UUID | None
    execution_id: uuid.UUID | None
    status: NotificationStatus
    attempt: int
    max_attempts: int
    error_message: str | None
    recipient: str | None
    created_at: datetime
    sent_at: datetime | None
    next_retry_at: datetime | None


class NotificationDeliveryDetail(NotificationDeliveryRead):
    payload: dict[str, Any]


class NotificationDeliveryPage(BaseModel):
    items: list[NotificationDeliveryRead]
    total: int
    limit: int
    offset: int
