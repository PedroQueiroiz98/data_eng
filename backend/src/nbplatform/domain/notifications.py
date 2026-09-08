"""Domínio de notificações: evento, tipo de provider, status e a mensagem canônica.

Central de Notificações (global). Qualquer produtor monta um `NotificationEvent`
(o envelope) e o `NotificationService` resolve os providers globais ativos e
despacha. Novos providers entram sem tocar nos Jobs nem no serviço.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class NotificationEventType(StrEnum):
    # implementados
    JOB_FAILED = "JOB_FAILED"
    WORKFLOW_FAILED = "WORKFLOW_FAILED"
    # preparados para o futuro (enum apenas, sem disparo)
    JOB_STARTED = "JOB_STARTED"
    JOB_SUCCESS = "JOB_SUCCESS"
    JOB_RETRY = "JOB_RETRY"
    WORKFLOW_STARTED = "WORKFLOW_STARTED"
    WORKFLOW_SUCCESS = "WORKFLOW_SUCCESS"
    WORKFLOW_RETRY = "WORKFLOW_RETRY"


class NotificationProviderType(StrEnum):
    EMAIL = "EMAIL"
    BITRIX = "BITRIX"


class NotificationStatus(StrEnum):
    PENDING = "PENDING"
    SENDING = "SENDING"
    SENT = "SENT"
    FAILED = "FAILED"


def idempotency_key(
    scope_id: str, provider_id: str, event_type: NotificationEventType
) -> str:
    """Ex.: `1842 + <provider-uuid> + JOB_FAILED` — evita envio duplicado.

    `scope_id` = `execution_id` quando existir, senão `job_id`.
    """
    return f"{scope_id}:{provider_id}:{event_type}"


@dataclass(frozen=True)
class NotificationEvent:
    """Envelope emitido por um componente que falhou. O serviço resolve o resto."""

    event_type: NotificationEventType
    occurred_at: datetime
    workflow_id: uuid.UUID | None = None
    job_id: uuid.UUID | None = None
    execution_id: uuid.UUID | None = None
    job_task_id: uuid.UUID | None = None

    @property
    def scope_id(self) -> str:
        return str(self.execution_id or self.job_id or "")


@dataclass
class NotificationMessage:
    """Modelo central entregue a todos os providers (spec §8)."""

    event_type: NotificationEventType
    title: str
    message: str
    environment: str
    pipeline_name: str
    job_name: str
    execution_id: str
    timestamp: datetime
    attempt: int = 1
    job_id: str | None = None
    workflow_id: str | None = None
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
