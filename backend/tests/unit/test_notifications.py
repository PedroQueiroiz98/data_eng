from __future__ import annotations

import json
from datetime import UTC, datetime

import httpx
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
from nbplatform.services.notifications.email_sender import OutgoingEmail
from nbplatform.services.notifications.providers.bitrix import (
    BitrixNotificationProvider,
    _attach,
    _endpoint,
    _message_text,
)
from nbplatform.services.notifications.providers.email import (
    EmailNotificationProvider,
    _default_subject,
    _html_body,
)
from nbplatform.services.notifications.resolved_settings import (
    BitrixProviderSettings,
    EmailProviderSettings,
    ResolvedSettings,
    resolve,
)
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


@pytest.mark.parametrize(
    "url,path,expected",
    [
        ("https://p.bitrix24.com", "/rest/1/abc/imbot.message.add",
         "https://p.bitrix24.com/rest/1/abc/imbot.message.add"),
        ("https://p.bitrix24.com/", "rest/1/abc/imbot.message.add",
         "https://p.bitrix24.com/rest/1/abc/imbot.message.add"),
        ("https://p.bitrix24.com/rest/1/abc/", "",
         "https://p.bitrix24.com/rest/1/abc/rest/imbot.message.add"),
        ("ignored", "https://full.example/rest/imbot.message.add",
         "https://full.example/rest/imbot.message.add"),
    ],
)
def test_bitrix_endpoint_join(url: str, path: str, expected: str) -> None:
    assert _endpoint(url, path, "imbot.message.add") == expected


def test_bitrix_endpoint_default_method_is_v2_when_path_blank() -> None:
    assert _endpoint("https://p.bitrix24.com", "", "imbot.v2.Chat.Message.send") == (
        "https://p.bitrix24.com/rest/imbot.v2.Chat.Message.send"
    )


def _bitrix_settings(*, bot: bool = True, path: str = "") -> ResolvedSettings:
    default_path = "/rest/1/abc/imbot.message.add" if bot else "/rest/1/abc/im.message.add"
    return ResolvedSettings(
        email=EmailProviderSettings(False, "", 0, "", "", "", True),
        bitrix=BitrixProviderSettings(
            enabled=True,
            url="https://p.bitrix24.com",
            send_message_path=path or default_path,
            bot_id="42" if bot else "",
            bot_token="tok" if bot else "",
        ),
    )


@pytest.mark.asyncio
async def test_bitrix_send_posts_expected_payload_and_reports_success() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"result": {"MESSAGE_ID": 1}})

    provider = BitrixNotificationProvider(
        client_factory=lambda _t: httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )
    cfg = NotificationConfig()
    cfg.bitrix_dialog_id = "chat3129"
    r = await provider.send(_msg(), cfg, _bitrix_settings())
    assert r.ok is True
    assert seen["url"] == "https://p.bitrix24.com/rest/1/abc/imbot.message.add"
    body = seen["body"]
    assert isinstance(body, dict)
    assert body["botId"] == "42" and body["botToken"] == "tok" and body["dialogId"] == "chat3129"
    assert "invalid date format" in body["fields"]["message"]
    assert body["fields"]["attach"][1]["GRID"]  # GRID presente


@pytest.mark.asyncio
async def test_bitrix_send_webhook_chat_mode_without_bot_credentials() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"result": 1})

    provider = BitrixNotificationProvider(
        client_factory=lambda _t: httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )
    cfg = NotificationConfig()
    cfg.bitrix_dialog_id = "chat3129"
    r = await provider.send(_msg(), cfg, _bitrix_settings(bot=False))
    assert r.ok is True
    assert seen["url"] == "https://p.bitrix24.com/rest/1/abc/im.message.add"
    body = seen["body"]
    assert isinstance(body, dict)
    assert body["DIALOG_ID"] == "chat3129"
    assert "invalid date format" in body["MESSAGE"]
    assert "botId" not in body and "botToken" not in body


@pytest.mark.asyncio
async def test_bitrix_send_surfaces_api_error_body() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"error": "BOT_ID_ERROR", "error_description": "Bot not found"}
        )

    provider = BitrixNotificationProvider(
        client_factory=lambda _t: httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )
    cfg = NotificationConfig()
    cfg.bitrix_dialog_id = "chat3129"
    r = await provider.send(_msg(), cfg, _bitrix_settings())
    assert r.ok is False
    assert "Bot not found" in (r.error or "")


@pytest.mark.asyncio
async def test_bitrix_send_reports_http_error_body() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="Not Found")

    provider = BitrixNotificationProvider(
        client_factory=lambda _t: httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )
    cfg = NotificationConfig()
    cfg.bitrix_dialog_id = "chat3129"
    r = await provider.send(_msg(), cfg, _bitrix_settings())
    assert r.ok is False
    assert "404" in (r.error or "") and "Not Found" in (r.error or "")
