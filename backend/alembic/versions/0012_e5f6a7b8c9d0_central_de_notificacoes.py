"""central de notificacoes: providers globais + deliveries

Substitui a arquitetura antiga de notificações por:
- notification_providers: lista global de providers (EMAIL/BITRIX), sem vínculo
  com Job/Workflow. Secret (senha SMTP / token Bitrix) em `secret_ct` (Fernet).
- notification_deliveries: histórico de tentativas de envio.

A linha `notification_settings` (se existir) é convertida em até um provider
EMAIL e um BITRIX, carregando o ciphertext Fernet verbatim. **Rode esta migração
ANTES de qualquer rotação de SECRET_ENCRYPTION_KEY**, senão o secret migrado não
decifra. As tabelas antigas (`notification_configs`, `notification_configurations`
e `notifications`) são descartadas sem migração de dados; o downgrade recria a
forma de referência (`notification_settings` + `notification_configs` +
`notifications`) vazia.

Revision ID: e5f6a7b8c9d0
Revises: c3d4e5f6a7b8
Create Date: 2026-09-08 00:30:00.000000+00:00
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "e5f6a7b8c9d0"
down_revision: str | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PROVIDER_TYPE = sa.Enum(
    "EMAIL", "BITRIX", name="notificationprovidertype", native_enum=False, length=20
)
_EVENT_TYPE = sa.Enum(
    "JOB_FAILED",
    "WORKFLOW_FAILED",
    "JOB_STARTED",
    "JOB_SUCCESS",
    "JOB_RETRY",
    "WORKFLOW_STARTED",
    "WORKFLOW_SUCCESS",
    "WORKFLOW_RETRY",
    name="notificationeventtype",
    native_enum=False,
    length=40,
)
_STATUS = sa.Enum(
    "PENDING", "SENDING", "SENT", "FAILED",
    name="notificationstatus", native_enum=False, length=20,
)


def upgrade() -> None:
    op.create_table(
        "notification_providers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.String(length=1000), nullable=True),
        sa.Column("provider_type", _PROVIDER_TYPE, nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
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
        sa.UniqueConstraint("name", name="uq_notification_provider_name"),
    )

    op.create_table(
        "notification_deliveries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("notification_provider_id", sa.Uuid(), nullable=True),
        sa.Column("provider_type", _PROVIDER_TYPE, nullable=False),
        sa.Column("event_type", _EVENT_TYPE, nullable=False),
        sa.Column("workflow_id", sa.Uuid(), nullable=True),
        sa.Column("job_id", sa.Uuid(), nullable=True),
        sa.Column("execution_id", sa.Uuid(), nullable=True),
        sa.Column("status", _STATUS, nullable=False, server_default="PENDING"),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("dedupe_key", sa.String(length=300), nullable=False),
        sa.Column("recipient", sa.String(length=500), nullable=True),
        sa.Column("sending_since", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("seq", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["notification_provider_id"],
            ["notification_providers.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["execution_id"], ["executions.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dedupe_key", name="uq_notification_delivery_dedupe"),
    )
    for col in ("notification_provider_id", "workflow_id", "job_id", "status", "created_at"):
        op.create_index(
            op.f(f"ix_notification_deliveries_{col}"),
            "notification_deliveries",
            [col],
            unique=False,
        )

    # ── converte notification_settings (se existir) em providers ───────────
    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
              IF EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'notification_settings'
              ) THEN
                INSERT INTO notification_providers
                    (id, name, description, provider_type, enabled,
                     configuration_json, secret_ct, created_at, updated_at)
                SELECT gen_random_uuid(), 'E-mail (migrado)', NULL, 'EMAIL',
                       (s.email_enabled AND s.smtp_host IS NOT NULL),
                       jsonb_build_object(
                           'host', s.smtp_host, 'port', s.smtp_port,
                           'username', s.smtp_username, 'from_email', s.smtp_from,
                           'from_name', NULL, 'use_tls', s.smtp_use_tls,
                           'recipients', COALESCE(s.default_email_recipients, '[]'::jsonb),
                           'cc', '[]'::jsonb, 'bcc', '[]'::jsonb),
                       s.smtp_password_ct, now(), now()
                FROM notification_settings s
                WHERE s.smtp_host IS NOT NULL;

                INSERT INTO notification_providers
                    (id, name, description, provider_type, enabled,
                     configuration_json, secret_ct, created_at, updated_at)
                SELECT gen_random_uuid(), 'Bitrix (migrado)', NULL, 'BITRIX',
                       (s.bitrix_enabled AND s.bitrix_url IS NOT NULL),
                       jsonb_build_object(
                           'url', s.bitrix_url,
                           'send_message_path', s.bitrix_send_message_path,
                           'bot_id', s.bitrix_bot_id,
                           'dialog_id', s.default_bitrix_dialog_id),
                       s.bitrix_bot_token_ct, now(), now()
                FROM notification_settings s
                WHERE s.bitrix_url IS NOT NULL;
              END IF;
            END $$;
            """
        )
    )

    # ── remove qualquer variante da arquitetura antiga ───────────────────
    op.execute("DROP TABLE IF EXISTS notifications CASCADE")
    op.execute("DROP TABLE IF EXISTS notification_configs CASCADE")
    op.execute("DROP TABLE IF EXISTS notification_configurations CASCADE")
    op.execute("DROP TABLE IF EXISTS notification_settings CASCADE")


def downgrade() -> None:
    op.create_table(
        "notification_settings",
        sa.Column("email_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("smtp_host", sa.String(length=255), nullable=True),
        sa.Column("smtp_port", sa.Integer(), nullable=True),
        sa.Column("smtp_username", sa.String(length=255), nullable=True),
        sa.Column("smtp_password_ct", sa.Text(), nullable=True),
        sa.Column("smtp_from", sa.String(length=320), nullable=True),
        sa.Column("smtp_use_tls", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("bitrix_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("bitrix_url", sa.String(length=500), nullable=True),
        sa.Column("bitrix_send_message_path", sa.String(length=255), nullable=True),
        sa.Column("bitrix_bot_id", sa.String(length=120), nullable=True),
        sa.Column("bitrix_bot_token_ct", sa.Text(), nullable=True),
        sa.Column(
            "default_on_failure", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column(
            "default_email_recipients",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("default_bitrix_dialog_id", sa.String(length=120), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "notification_configs",
        sa.Column("workflow_id", sa.Uuid(), nullable=False),
        sa.Column("on_failure", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("on_success", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("on_retry", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("on_cancelled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("on_started", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("email_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "email_recipients",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "email_cc",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "email_bcc",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("email_subject", sa.String(length=300), nullable=True),
        sa.Column("bitrix_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("bitrix_dialog_id", sa.String(length=120), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workflow_id"),
    )
    op.create_table(
        "notifications",
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_id", sa.Uuid(), nullable=True),
        sa.Column("execution_id", sa.Uuid(), nullable=True),
        sa.Column("channel", sa.String(length=20), nullable=False),
        sa.Column("event_type", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("recipient", sa.String(length=500), nullable=True),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sending_since", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("seq", sa.BigInteger(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["execution_id"], ["executions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "job_id", "event_type", "channel", name="uq_notification_idempotency"
        ),
    )
    op.create_index(
        op.f("ix_notifications_job_id"), "notifications", ["job_id"], unique=False
    )

    for col in ("created_at", "status", "job_id", "workflow_id", "notification_provider_id"):
        op.drop_index(
            op.f(f"ix_notification_deliveries_{col}"),
            table_name="notification_deliveries",
        )
    op.drop_table("notification_deliveries")
    op.drop_table("notification_providers")
