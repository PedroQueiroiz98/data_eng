from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from nbplatform.db.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin
from nbplatform.domain.enums import ExecutionSource, ExecutionStatus, LogLevel


class Execution(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "executions"
    __table_args__ = (
        Index("ix_executions_status_created", "status", "created_at"),
        Index("ix_executions_heartbeat", "status", "last_heartbeat"),
        Index("ix_executions_workspace", "workspace_id", "created_at"),
    )

    # Discriminador de origem do notebook. DB (legado) usa notebook_version_id;
    # WORKSPACE usa workspace_id + notebook_path. Invariante garantida no serviço.
    source: Mapped[ExecutionSource] = mapped_column(
        Enum(ExecutionSource, native_enum=False, length=20),
        default=ExecutionSource.DB,
        server_default=ExecutionSource.DB.value,
        nullable=False,
    )
    notebook_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("notebook_versions.id", ondelete="RESTRICT"), index=True
    )
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("workspaces.id", ondelete="RESTRICT"), index=True
    )
    # Caminho do notebook relativo à raiz do Workspace (POSIX).
    notebook_path: Mapped[str | None] = mapped_column(String(1024))
    # SHA do commit no momento da execução (preenchido quando há repositório Git).
    source_commit: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[ExecutionStatus] = mapped_column(
        Enum(ExecutionStatus, native_enum=False, length=20),
        default=ExecutionStatus.QUEUED,
        nullable=False,
    )
    parameters: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(200), unique=True)
    # Overrides opcionais (execução disparada por Job herda da workflow_task).
    retry_policy: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    timeout_s: Mapped[int | None] = mapped_column(Integer)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(BigInteger)

    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(Text)
    output_notebook_path: Mapped[str | None] = mapped_column(Text)
    # Conteúdo do output.ipynb (para visualizar a execução depois, servido pela API).
    output_notebook: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    worker_id: Mapped[str | None] = mapped_column(String(100), index=True)
    last_heartbeat: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    logs: Mapped[list[ExecutionLog]] = relationship(
        back_populates="execution", cascade="all, delete-orphan"
    )


class ExecutionLog(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "execution_logs"
    __table_args__ = (Index("ix_execution_logs_exec_seq", "execution_id", "seq"),)

    execution_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("executions.id", ondelete="CASCADE"), nullable=False
    )
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    level: Mapped[LogLevel] = mapped_column(
        Enum(LogLevel, native_enum=False, length=10), default=LogLevel.INFO, nullable=False
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    # Cursor monotônico por execução para replay via WebSocket.
    seq: Mapped[int] = mapped_column(BigInteger, nullable=False)

    execution: Mapped[Execution] = relationship(back_populates="logs")
