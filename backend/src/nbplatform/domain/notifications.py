"""Domínio de notificações: evento, canal, status e a mensagem canônica.

Desacoplado dos Jobs: qualquer produtor monta uma `NotificationMessage` e o
`NotificationService` decide os canais. Novos canais entram sem tocar nos Jobs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class NotificationEvent(StrEnum):
    JOB_FAILED = "JOB_FAILED"
    # preparados para o futuro (config já aceita, disparo ainda não implementado)
    JOB_SUCCESS = "JOB_SUCCESS"
    JOB_RETRY = "JOB_RETRY"
    JOB_CANCELLED = "JOB_CANCELLED"
    JOB_STARTED = "JOB_STARTED"


class NotificationChannel(StrEnum):
    EMAIL = "EMAIL"
    BITRIX = "BITRIX"


class NotificationStatus(StrEnum):
    PENDING = "PENDING"
    SENDING = "SENDING"
    SENT = "SENT"
    FAILED = "FAILED"


def idempotency_key(job_id: str, event: NotificationEvent, channel: NotificationChannel) -> str:
    """Ex.: `1842 + JOB_FAILED + BITRIX` — evita envio duplicado do mesmo evento."""
    return f"{job_id}:{event}:{channel}"


@dataclass
class NotificationMessage:
    """Modelo central entregue a todos os providers (spec §8)."""

    event_type: NotificationEvent
    title: str
    message: str
    environment: str
    pipeline_name: str
    job_name: str
    execution_id: str
    timestamp: datetime
    attempt: int = 1
    error_type: str | None = None
    error_message: str | None = None
    correlation_id: str | None = None
    duration_ms: int | None = None
    notebook_name: str | None = None
    execution_url: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderResult:
    ok: bool
    detail: str = ""
    error: str | None = None

    @classmethod
    def success(cls, detail: str = "") -> ProviderResult:
        return cls(ok=True, detail=detail)

    @classmethod
    def failure(cls, error: str) -> ProviderResult:
        return cls(ok=False, error=error)
