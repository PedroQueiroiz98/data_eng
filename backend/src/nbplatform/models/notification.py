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
    NotificationChannel,
    NotificationEvent,
    NotificationStatus,
)


class NotificationConfig(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Configuração de notificação por Workflow/Pipeline. Sem secrets aqui."""

    __tablename__ = "notification_configs"

    workflow_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workflows.id", ondelete="CASCADE"), unique=True, nullable=False
    )

    on_failure: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    on_success: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    on_retry: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    on_cancelled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    on_started: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # e-mail
    email_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    email_recipients: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    email_cc: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    email_bcc: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    email_subject: Mapped[str | None] = mapped_column(String(300))

    # bitrix (apenas referências permitidas; token fica no NotificationSettings)
    bitrix_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    bitrix_dialog_id: Mapped[str | None] = mapped_column(String(120))


class NotificationSettings(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Configuração global dos providers (linha única). Secrets cifrados."""

    __tablename__ = "notification_settings"

    # SMTP
    email_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    smtp_host: Mapped[str | None] = mapped_column(String(255))
    smtp_port: Mapped[int | None] = mapped_column(Integer)
    smtp_username: Mapped[str | None] = mapped_column(String(255))
    smtp_password_ct: Mapped[str | None] = mapped_column(Text)  # Fernet
    smtp_from: Mapped[str | None] = mapped_column(String(320))
    smtp_use_tls: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Bitrix
    bitrix_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    bitrix_url: Mapped[str | None] = mapped_column(String(500))
    bitrix_send_message_path: Mapped[str | None] = mapped_column(String(255))
    bitrix_bot_id: Mapped[str | None] = mapped_column(String(120))
    bitrix_bot_token_ct: Mapped[str | None] = mapped_column(Text)  # Fernet

    # Fallback: notifica falha de qualquer pipeline sem NotificationConfig próprio.
    default_on_failure: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    default_email_recipients: Mapped[list[str]] = mapped_column(
        JSONB, default=list, nullable=False
    )
    default_bitrix_dialog_id: Mapped[str | None] = mapped_column(String(120))


class Notification(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Histórico de envio (spec §14)."""

    __tablename__ = "notifications"
    __table_args__ = (
        UniqueConstraint(
            "job_id", "event_type", "channel", name="uq_notification_idempotency"
        ),
    )

    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    workflow_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("workflows.id", ondelete="SET NULL")
    )
    execution_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("executions.id", ondelete="SET NULL")
    )
    channel: Mapped[NotificationChannel] = mapped_column(
        Enum(NotificationChannel, native_enum=False, length=20), nullable=False
    )
    event_type: Mapped[NotificationEvent] = mapped_column(
        Enum(NotificationEvent, native_enum=False, length=30), nullable=False
    )
    status: Mapped[NotificationStatus] = mapped_column(
        Enum(NotificationStatus, native_enum=False, length=20),
        default=NotificationStatus.PENDING,
        nullable=False,
    )
    recipient: Mapped[str | None] = mapped_column(String(500))
    attempt: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # cópia enxuta da mensagem para reenvio manual sem recalcular contexto
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    seq: Mapped[int | None] = mapped_column(BigInteger)
