from __future__ import annotations

from datetime import UTC, datetime

import pytest

from nbplatform.core.config import Settings
from nbplatform.core.crypto import SecretCipher
from nbplatform.domain.notifications import (
    NotificationChannel,
    NotificationEvent,
    NotificationMessage,
    idempotency_key,
)
from nbplatform.models.notification import NotificationConfig, NotificationSettings
from nbplatform.services.notifications.email_sender import EmailProviderSettings, OutgoingEmail
from nbplatform.services.notifications.providers.bitrix import _attach, _message_text
from nbplatform.services.notifications.providers.email import (
    EmailNotificationProvider,
    _default_subject,
    _html_body,
)
from nbplatform.services.notifications.resolved_settings import resolve
from nbplatform.services.notifications.service import (
    _deserialize,
    _enabled_channels,
    _serialize,
)

KEY = "iY0uDAIk3AqhPlmaVTZOGf-Bajj5kjmIDRZiwqRLvDc="


def _msg() -> NotificationMessage:
    return NotificationMessage(
        event_type=NotificationEvent.JOB_FAILED,
        title="🚨 Falha na execução do Job",
        message="corpo",
        environment="production",
        pipeline_name="Customer ETL",
        job_name="Execute Notebook",
        execution_id="1842",
        timestamp=datetime(2026, 9, 7, 12, 6, 13, tzinfo=UTC),
        attempt=2,
        error_type="ValueError",
        error_message="invalid date format",
        correlation_id="job-1",
        duration_ms=102_000,
        notebook_name="customer_etl.ipynb",
        execution_url="http://app/jobs/job-1",
        metadata={"Ambiente": "production", "Erro": "invalid date format"},
    )


def test_idempotency_key() -> None:
    assert (
        idempotency_key("1842", NotificationEvent.JOB_FAILED, NotificationChannel.BITRIX)
        == "1842:JOB_FAILED:BITRIX"
    )


def test_serialize_roundtrip() -> None:
    out = _deserialize(_serialize(_msg()))
    assert out.event_type is NotificationEvent.JOB_FAILED
    assert out.pipeline_name == "Customer ETL"
    assert out.timestamp == _msg().timestamp
    assert out.metadata["Erro"] == "invalid date format"


def test_enabled_channels_respects_event_flag_and_channels() -> None:
    cfg = NotificationConfig()
    cfg.on_failure = False
    cfg.email_enabled = True
    cfg.bitrix_enabled = True
    assert _enabled_channels(cfg, NotificationEvent.JOB_FAILED) == []

    cfg.on_failure = True
    assert _enabled_channels(cfg, NotificationEvent.JOB_FAILED) == [
        NotificationChannel.EMAIL,
        NotificationChannel.BITRIX,
    ]

    cfg.bitrix_enabled = False
    assert _enabled_channels(cfg, NotificationEvent.JOB_FAILED) == [NotificationChannel.EMAIL]
    assert _enabled_channels(None, NotificationEvent.JOB_FAILED) == []


def test_resolve_uses_env_fallback_and_never_exposes_secret_object() -> None:
    settings = Settings(
        secret_encryption_key=KEY,
        notify_smtp_host="smtp.local",
        notify_smtp_from="ci@x.com",
        notify_bitrix_url="https://b24.example",
        notify_bitrix_bot_id="42",
        notify_bitrix_bot_token="env-token",
    )
    r = resolve(None, settings, SecretCipher(KEY))
    assert r.email.usable is True
    assert r.bitrix.usable is True
    assert r.bitrix.bot_token == "env-token"  # só existe aqui, no envio


def test_resolve_decrypts_db_secret_over_env() -> None:
    cipher = SecretCipher(KEY)
    row = NotificationSettings()
    row.bitrix_enabled = True
    row.bitrix_url = "https://db.example"
    row.bitrix_bot_id = "7"
    row.bitrix_bot_token_ct = cipher.encrypt("db-token")
    r = resolve(row, Settings(secret_encryption_key=KEY), cipher)
    assert r.bitrix.bot_token == "db-token"


def test_email_subject_and_body_no_secret_leak() -> None:
    m = _msg()
    assert _default_subject(m) == "[JOB FAILED] Customer ETL - Execute Notebook"
    body = _html_body(m)
    assert "invalid date format" in body
    assert "View Execution" in body
    assert "token" not in body.lower()


@pytest.mark.asyncio
async def test_email_provider_isolated_failure_without_recipients() -> None:
    class FakeSender:
        async def send(self, email: OutgoingEmail, settings: EmailProviderSettings) -> None:
            raise AssertionError("não deveria enviar sem destinatário")

    provider = EmailNotificationProvider(FakeSender())
    cfg = NotificationConfig()
    cfg.email_recipients = []
    r = resolve(None, Settings(secret_encryption_key=KEY), SecretCipher(KEY))
    result = await provider.send(_msg(), cfg, r)
    assert result.ok is False
    assert "destinat" in (result.error or "")


@pytest.mark.asyncio
async def test_email_provider_sends_via_injected_sender() -> None:
    sent: list[OutgoingEmail] = []

    class FakeSender:
        async def send(self, email: OutgoingEmail, settings: EmailProviderSettings) -> None:
            sent.append(email)

    provider = EmailNotificationProvider(FakeSender())
    cfg = NotificationConfig()
    cfg.email_recipients = ["pedro@x.com"]
    cfg.email_cc = ["devops@x.com"]
    cfg.email_subject = None
    settings = Settings(
        secret_encryption_key=KEY, notify_smtp_host="smtp.local", notify_smtp_from="ci@x.com"
    )
    r = resolve(None, settings, SecretCipher(KEY))
    result = await provider.send(_msg(), cfg, r)
    assert result.ok is True
    assert sent[0].to == ["pedro@x.com"]
    assert sent[0].cc == ["devops@x.com"]
    assert sent[0].subject == "[JOB FAILED] Customer ETL - Execute Notebook"


def test_bitrix_attach_has_all_grid_fields_and_error_in_message() -> None:
    m = _msg()
    attach = _attach(m)
    assert attach[0]["DELIMITER"]["COLOR"] == "#e01e5a"
    grid = attach[1]["GRID"]
    names = {row["NAME"] for row in grid}
    assert {"Ambiente", "Erro", "Pipeline", "Job", "Execution ID", "Attempt", "Duration"} <= names
    assert "invalid date format" in _message_text(m)
