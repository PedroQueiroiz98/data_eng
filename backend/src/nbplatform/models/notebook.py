from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from nbplatform.db.base import Base, CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin


class Notebook(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "notebooks"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    current_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )

    versions: Mapped[list[NotebookVersion]] = relationship(
        back_populates="notebook",
        cascade="all, delete-orphan",
        order_by="NotebookVersion.version_number",
    )


class NotebookVersion(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Versão imutável do notebook — cada Execution aponta para uma destas."""

    __tablename__ = "notebook_versions"
    __table_args__ = (
        UniqueConstraint("notebook_id", "version_number", name="uq_notebook_version"),
    )

    notebook_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("notebooks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    # Conteúdo .ipynb completo (nbformat v4).
    content: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    notebook: Mapped[Notebook] = relationship(back_populates="versions")
