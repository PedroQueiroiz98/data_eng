from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from nbplatform.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class UserGitHubAccount(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Conta do GitHub conectada por um usuário ao seu Workspace pessoal.

    Modelo single-workspace-por-usuário: o vínculo é 1:1 com `user_id` (não com
    um `Workspace.id` — ver `WorkspaceGitRepository`, que é resquício do modelo
    multi-tenant anterior e não é usado). O PAT fica só em `token_ct` (Fernet,
    mesma `SecretCipher` dos providers de IA/notificação); nunca em texto claro
    fora da memória do processo durante uma chamada, nunca retornado pela API.
    """

    __tablename__ = "user_github_accounts"
    __table_args__ = (UniqueConstraint("user_id", name="uq_user_github_account_user"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_ct: Mapped[str] = mapped_column(Text, nullable=False)
    github_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    github_username: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320))
    avatar_url: Mapped[str | None] = mapped_column(String(500))

    # vínculo de repositório — preenchido ao "Inicializar Repositório no Workspace"
    repo_full_name: Mapped[str | None] = mapped_column(String(300))  # "owner/repo"
    repo_default_branch: Mapped[str | None] = mapped_column(String(200))
    base_dir: Mapped[str] = mapped_column(
        String(500), nullable=False, default="", server_default=""
    )
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
