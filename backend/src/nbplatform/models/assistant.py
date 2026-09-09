from __future__ import annotations

import uuid

from sqlalchemy import (
    Boolean,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from nbplatform.db.base import Base, CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin
from nbplatform.domain.assistant import AssistantProviderType, AssistantTask


class AssistantProvider(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Provider de IA global (config da UI /assistant, admin).

    A API key fica SÓ em `secret_ct` (Fernet) — nunca em `configuration_json`,
    nunca retornada pela API, nunca logada.
    """

    __tablename__ = "assistant_providers"
    __table_args__ = (UniqueConstraint("name", name="uq_assistant_provider_name"),)

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000))
    provider_type: Mapped[AssistantProviderType] = mapped_column(
        Enum(AssistantProviderType, native_enum=False, length=20), nullable=False
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    configuration_json: Mapped[dict[str, object]] = mapped_column(
        JSONB, default=dict, nullable=False
    )
    secret_ct: Mapped[str | None] = mapped_column(Text)  # Fernet ciphertext


class AssistantInteraction(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Histórico de uma interação de IA ligada a um notebook (spec §16)."""

    __tablename__ = "assistant_interactions"
    __table_args__ = (
        Index("ix_assistant_interactions_created_at", "created_at"),
    )

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    provider_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("assistant_providers.id", ondelete="SET NULL")
    )
    provider_type: Mapped[AssistantProviderType | None] = mapped_column(
        Enum(AssistantProviderType, native_enum=False, length=20)
    )
    task: Mapped[AssistantTask] = mapped_column(
        Enum(AssistantTask, native_enum=False, length=20), nullable=False
    )
    notebook_path: Mapped[str | None] = mapped_column(String(1024))
    cell_id: Mapped[str | None] = mapped_column(String(64))
    model: Mapped[str | None] = mapped_column(String(120))
    prompt_chars: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completion_chars: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    completion_tokens: Mapped[int | None] = mapped_column(Integer)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    ok: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
    # só preenchido quando `assistant_store_result_text` (prompt NUNCA é gravado)
    result_text: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(String(200))
