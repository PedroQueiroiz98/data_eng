"""assistente de IA: providers globais + histórico de interações

- assistant_providers: OpenAI / Azure OpenAI / Ollama, configurados pela UI
  (/assistant, admin). A API key fica em `secret_ct` (Fernet), nunca no JSON.
- assistant_interactions: histórico por notebook (métricas + texto gerado
  quando `ASSISTANT_STORE_RESULT_TEXT`; o prompt NUNCA é persistido).

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-09-09 00:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b8c9d0e1f2a3"
down_revision: str | None = "a7b8c9d0e1f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PROVIDER_TYPE = sa.Enum(
    "OPENAI", "AZURE_OPENAI", "OLLAMA",
    name="assistantprovidertype", native_enum=False, length=20,
)
_TASK = sa.Enum(
    "GENERATE", "EXPLAIN", "FIX", "OPTIMIZE", "TESTS", "CONTINUE",
    "CONVERT", "DOCSTRING", "CHAT", "INLINE",
    name="assistanttask", native_enum=False, length=20,
)


def upgrade() -> None:
    op.create_table(
        "assistant_providers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.String(length=1000), nullable=True),
        sa.Column("provider_type", _PROVIDER_TYPE, nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "configuration_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("secret_ct", sa.Text(), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_assistant_provider_name"),
    )

    op.create_table(
        "assistant_interactions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("provider_id", sa.Uuid(), nullable=True),
        sa.Column("provider_type", _PROVIDER_TYPE, nullable=True),
        sa.Column("task", _TASK, nullable=False),
        sa.Column("notebook_path", sa.String(length=1024), nullable=True),
        sa.Column("cell_id", sa.String(length=64), nullable=True),
        sa.Column("model", sa.String(length=120), nullable=True),
        sa.Column("prompt_chars", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completion_chars", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("ok", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("result_text", sa.Text(), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["provider_id"], ["assistant_providers.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_assistant_interactions_user_id"),
        "assistant_interactions",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_assistant_interactions_created_at"),
        "assistant_interactions",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_assistant_interactions_created_at"), table_name="assistant_interactions"
    )
    op.drop_index(
        op.f("ix_assistant_interactions_user_id"), table_name="assistant_interactions"
    )
    op.drop_table("assistant_interactions")
    op.drop_table("assistant_providers")
