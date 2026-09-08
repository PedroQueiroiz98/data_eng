from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from nbplatform.db.base import Base, CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin
from nbplatform.domain.notifications import (
    NotificationEventType,
    NotificationProviderType,
    NotificationStatus,
)


class NotificationProvider(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Provider global de notificação (Central de Notificações).

    Sem vínculo com Job/Workflow/Pipeline/Notebook — é configuração global.
    Secrets (senha SMTP, token Bitrix) ficam SÓ em `secret_ct` (Fernet), nunca
    em `configuration_json`, nunca retornados pela API, nunca logados.
    """

    __tablename__ = "notification_providers"
    __table_args__ = (UniqueConstraint("name", name="uq_notification_provider_name"),)

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000))
    provider_type: Mapped[NotificationProviderType] = mapped_column(
        Enum(NotificationProviderType, native_enum=False, length=20), nullable=False
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    configuration_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    secret_ct: Mapped[str | None] = mapped_column(Text)  # Fernet ciphertext


class NotificationDelivery(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Uma tentativa de envio de um evento por um provider (spec §17).

    `workflow_id`/`job_id`/`execution_id` são só auditoria/rastreio — não
    transformam o provider em configuração vinculada.
    """

    __tablename__ = "notification_deliveries"
    __table_args__ = (UniqueConstraint("dedupe_key", name="uq_notification_delivery_dedupe"),)

    notification_provider_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("notification_providers.id", ondelete="SET NULL"), index=True
    )
    provider_type: Mapped[NotificationProviderType] = mapped_column(
        Enum(NotificationProviderType, native_enum=False, length=20), nullable=False
    )
    event_type: Mapped[NotificationEventType] = mapped_column(
        Enum(NotificationEventType, native_enum=False, length=40), nullable=False
    )
    workflow_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("workflows.id", ondelete="SET NULL"), index=True
    )
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("jobs.id", ondelete="SET NULL"), index=True
    )
    execution_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("executions.id", ondelete="SET NULL")
    )
    status: Mapped[NotificationStatus] = mapped_column(
        Enum(NotificationStatus, native_enum=False, length=20),
        default=NotificationStatus.PENDING,
        nullable=False,
        index=True,
    )
    attempt: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    dedupe_key: Mapped[str] = mapped_column(String(300), nullable=False)
    recipient: Mapped[str | None] = mapped_column(String(500))
    # marcado ao entrar em SENDING; recovery detecta envios abandonados. Limpo
    # em qualquer estado terminal ou ao voltar para PENDING.
    sending_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # cópia enxuta da mensagem para reenvio manual sem recalcular contexto
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    seq: Mapped[int | None] = mapped_column(BigInteger)
