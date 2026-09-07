from __future__ import annotations

from sqlalchemy import String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from nbplatform.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Variable(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "variables"
    __table_args__ = (UniqueConstraint("key", "scope", name="uq_variable_key_scope"),)

    key: Mapped[str] = mapped_column(String(200), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    scope: Mapped[str] = mapped_column(String(100), default="global", nullable=False)


class Secret(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Valor sempre criptografado em repouso; nunca retornado pela API."""

    __tablename__ = "secrets"

    key: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
