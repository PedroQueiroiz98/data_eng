from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from nbplatform.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from nbplatform.domain.enums import GitProvider


class Workspace(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "workspaces"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    # Raiz física; sempre derivada do UUID (rename não toca no disco).
    root_path: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )

    git_repository: Mapped[WorkspaceGitRepository | None] = relationship(
        back_populates="workspace", cascade="all, delete-orphan", uselist=False
    )


class WorkspaceGitRepository(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Associação de um Workspace a um repositório remoto (GitHub por ora).

    O token de acesso (PAT) é cifrado em repouso (`SecretCipher`); nunca volta
    para o frontend nem para os logs.
    """

    __tablename__ = "workspace_git_repositories"
    __table_args__ = (
        UniqueConstraint("workspace_id", name="uq_workspace_git_repo_workspace"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[GitProvider] = mapped_column(
        Enum(GitProvider, native_enum=False, length=20),
        default=GitProvider.GITHUB,
        nullable=False,
    )
    repo_url: Mapped[str] = mapped_column(String(500), nullable=False)
    repo_name: Mapped[str | None] = mapped_column(String(200))
    repo_owner: Mapped[str | None] = mapped_column(String(200))
    default_branch: Mapped[str | None] = mapped_column(String(200))
    current_branch: Mapped[str | None] = mapped_column(String(200))
    access_token_ct: Mapped[str | None] = mapped_column(Text)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    workspace: Mapped[Workspace] = relationship(back_populates="git_repository")
