"""integração GitHub: conta pessoal do usuário (PAT cifrado) + vínculo de repo

- user_github_accounts: 1:1 com `user_id` (modelo single-workspace-por-usuário
  — não usa `WorkspaceGitRepository`, que é resquício do modelo multi-tenant
  anterior). O PAT fica só em `token_ct` (Fernet), nunca em texto claro.

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-09-09 00:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c9d0e1f2a3b4"
down_revision: str | None = "b8c9d0e1f2a3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_github_accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_ct", sa.Text(), nullable=False),
        sa.Column("github_user_id", sa.BigInteger(), nullable=False),
        sa.Column("github_username", sa.String(length=200), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("avatar_url", sa.String(length=500), nullable=True),
        sa.Column("repo_full_name", sa.String(length=300), nullable=True),
        sa.Column("repo_default_branch", sa.String(length=200), nullable=True),
        sa.Column("base_dir", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_user_github_account_user"),
    )
    op.create_index(
        op.f("ix_user_github_accounts_user_id"), "user_github_accounts", ["user_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_user_github_accounts_user_id"), table_name="user_github_accounts")
    op.drop_table("user_github_accounts")
