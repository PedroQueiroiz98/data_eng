from __future__ import annotations

import json
from datetime import UTC, datetime

import httpx
import pytest

from nbplatform.domain.notifications import (
    NotificationEventType,
    NotificationMessage,
    NotificationProviderType,
    ProviderResult,
    idempotency_key,
)
from nbplatform.services.notifications.email_sender import (
    EmailProviderSettings,
    OutgoingEmail,
)
from nbplatform.services.notifications.providers import ConfigError, ResolvedTarget
from nbplatform.services.notifications.providers.bitrix import (
    BitrixNotificationProvider,
    _attach,
    _endpoint,
    _message_text,
)
from nbplatform.services.notifications.providers.email import (
    EmailNotificationProvider,
    _html_body,
    _subject,
)
from nbplatform.services.notifications.registry import (
    NotificationProviderRegistry,
    UnknownProviderType,
    default_registry,
)
from nbplatform.services.notifications.service import _deserialize, _serialize

KEY = "iY0uDAIk3AqhPlmaVTZOGf-Bajj5kjmIDRZiwqRLvDc="


def _msg() -> NotificationMessage:
    return NotificationMessage(
        event_type=NotificationEventType.JOB_FAILED,
        title="🚨 Etapa do pipeline falhou",
        message="corpo",
        environment="production",
        pipeline_name="Customer ETL",
        job_name="Transformation",
        execution_id="1842",
        timestamp=datetime(2026, 9, 7, 12, 6, 13, tzinfo=UTC),
        attempt=2,
        job_id="job-1",
        workflow_id="wf-1",
        error_type="ConnectionException",
        error_message="Connection timeout",
        correlation_id="job-1",
        duration_ms=102_000,
        notebook_name="customer_etl.ipynb",
        execution_url="http://app/jobs/job-1",
        metadata={
            "Ambiente": "production",
            "Erro": "Connection timeout",
            "Componente": "PostgreSQL",
            "Workflow": "Customer ETL",
            "Job": "Transformation",
            "Execution ID": "1842",
            "Attempt": "2",
            "Duration": "1m 42s",
        },
    )


# ── domínio ────────────────────────────────────────────────────────────────
def test_idempotency_key_scopes_by_execution_or_job() -> None:
    assert (
        idempotency_key("1842", "prov-9", NotificationEventType.JOB_FAILED)
        == "1842:prov-9:JOB_FAILED"
    )


def test_serialize_roundtrip_keeps_new_fields() -> None:
    out = _deserialize(_serialize(_msg()))
    assert out.event_type is NotificationEventType.JOB_FAILED
    assert out.pipeline_name == "Customer ETL"
    assert out.job_id == "job-1" and out.workflow_id == "wf-1"
    assert out.timestamp == _msg().timestamp
    assert out.metadata["Erro"] == "Connection timeout"


# ── registry (spec §10) ───────────────────────────────────────────────────
def test_registry_resolves_type_without_branching() -> None:
    reg = default_registry()
    assert reg.get("EMAIL").provider_type == "EMAIL"
    assert reg.get("BITRIX").provider_type == "BITRIX"
    assert reg.has("SLACK") is False
    with pytest.raises(UnknownProviderType):
        reg.get("SLACK")
    assert set(reg.types()) == {"EMAIL", "BITRIX"}


def test_registry_accepts_a_new_provider_type() -> None:
    class FakeSender:
        provider_type = "FAKE"

        def validate_config(self, config, *, has_secret):  # noqa: ANN001, D401
            return None

        def summary(self, config):  # noqa: ANN001
            return "fake"

        def targets(self, target):  # noqa: ANN001
            return ["x"]

        async def send(self, message, target, *, timeout_s):  # noqa: ANN001
            return ProviderResult.success("fake ok")

    reg = NotificationProviderRegistry([FakeSender()])
    assert reg.has("FAKE")
    assert reg.get("FAKE").summary({}) == "fake"


# ── email sender (spec §12/§15) ──────────────────────────────────────────
class _FakeEmailSender:
    def __init__(self) -> None:
        self.sent: list[OutgoingEmail] = []
        self.settings: EmailProviderSettings | None = None

    async def send(self, email: OutgoingEmail, settings: EmailProviderSettings) -> None:
        self.sent.append(email)
        self.settings = settings


def _email_target(**overrides) -> ResolvedTarget:
    cfg = {
        "host": "smtp.empresa.com",
        "port": 587,
        "username": "notification",
        "from_email": "noreply@empresa.com",
        "from_name": "Data Platform",
        "use_tls": True,
        "recipients": ["data-team@empresa.com", "suporte@empresa.com"],
        "cc": ["devops@empresa.com"],
        "bcc": [],
    }
    cfg.update(overrides)
    return ResolvedTarget(provider_id="p1", config=cfg, secret="smtp-secret")


@pytest.mark.asyncio
async def test_email_sender_builds_from_configuration_json() -> None:
    fake = _FakeEmailSender()
    provider = EmailNotificationProvider(fake)
    result = await provider.send(_msg(), _email_target(), timeout_s=5)
    assert result.ok is True
    assert fake.sent[0].to == ["data-team@empresa.com", "suporte@empresa.com"]
    assert fake.sent[0].cc == ["devops@empresa.com"]
    assert fake.settings is not None
    assert fake.settings.password == "smtp-secret"
    assert fake.settings.from_email == "noreply@empresa.com"


def test_email_subject_and_body_no_secret_leak() -> None:
    m = _msg()
    assert _subject(m) == "[JOB FAILED] Customer ETL - Transformation"
    body = _html_body(m)
    assert "Connection timeout" in body
    assert "Abrir execução" in body
    assert "secret" not in body.lower() and "smtp-secret" not in body


@pytest.mark.asyncio
async def test_email_provider_fails_without_recipients() -> None:
    provider = EmailNotificationProvider(_FakeEmailSender())
    result = await provider.send(_msg(), _email_target(recipients=[]), timeout_s=5)
    assert result.ok is False
    assert "destinat" in (result.error or "")


@pytest.mark.asyncio
async def test_email_provider_timeout_becomes_failed_result() -> None:
    import asyncio

    class SlowSender:
        async def send(self, email, settings):  # noqa: ANN001
            await asyncio.sleep(1)

    provider = EmailNotificationProvider(SlowSender())
    result = await provider.send(_msg(), _email_target(), timeout_s=0.05)
    assert result.ok is False
    assert "timeout" in (result.error or "")


def test_email_validate_config_requires_host_and_recipients() -> None:
    p = EmailNotificationProvider(_FakeEmailSender())
    with pytest.raises(ConfigError):
        p.validate_config({"from_email": "x@y.com", "recipients": ["a@b.com"]}, has_secret=True)
    with pytest.raises(ConfigError):
        p.validate_config({"host": "smtp", "from_email": "x@y.com"}, has_secret=True)
    p.validate_config(
        {"host": "smtp", "from_email": "x@y.com", "recipients": ["a@b.com"]},
        has_secret=True,
    )


# ── bitrix sender (spec §13/§14) ─────────────────────────────────────────
def _bitrix_target(*, bot: bool = True, dialog_id: str = "chat3129") -> ResolvedTarget:
    cfg = {
        "url": "https://empresa.bitrix24.com.br",
        "send_message_path": (
            "/rest/1/abc/imbot.message.add" if bot else "/rest/1/abc/im.message.add"
        ),
        "bot_id": "93" if bot else "",
        "dialog_id": dialog_id,
    }
    return ResolvedTarget(provider_id="p2", config=cfg, secret="bot-token" if bot else "")


def test_bitrix_validate_config_requires_url_and_dialog() -> None:
    p = BitrixNotificationProvider()
    with pytest.raises(ConfigError):
        p.validate_config({"dialog_id": "chat1"}, has_secret=True)
    with pytest.raises(ConfigError):
        p.validate_config({"url": "https://x"}, has_secret=True)
    p.validate_config({"url": "https://x", "dialog_id": "chat1"}, has_secret=True)


def test_bitrix_attach_has_grid_and_error_in_message() -> None:
    m = _msg()
    attach = _attach(m)
    assert attach[0]["DELIMITER"]["COLOR"] == "#e01e5a"
    names = {row["NAME"] for row in attach[1]["GRID"]}
    assert {"Ambiente", "Erro", "Workflow", "Job", "Execution ID", "Attempt"} <= names
    assert "Connection timeout" in _message_text(m)


@pytest.mark.parametrize(
    "url,path,expected",
    [
        ("https://p.bitrix24.com", "/rest/1/abc/imbot.message.add",
         "https://p.bitrix24.com/rest/1/abc/imbot.message.add"),
        ("https://p.bitrix24.com/", "rest/1/abc/imbot.message.add",
         "https://p.bitrix24.com/rest/1/abc/imbot.message.add"),
        ("ignored", "https://full.example/rest/imbot.message.add",
         "https://full.example/rest/imbot.message.add"),
    ],
)
def test_bitrix_endpoint_join(url: str, path: str, expected: str) -> None:
    assert _endpoint(url, path, "imbot.message.add") == expected


@pytest.mark.asyncio
async def test_bitrix_send_bot_mode_payload_and_masks_token_in_logs(caplog) -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"result": {"MESSAGE_ID": 1}})

    provider = BitrixNotificationProvider(
        client_factory=lambda _t: httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )
    with caplog.at_level("INFO"):
        r = await provider.send(_msg(), _bitrix_target(), timeout_s=5)
    assert r.ok is True
    body = seen["body"]
    assert isinstance(body, dict)
    assert body["botId"] == "93" and body["botToken"] == "bot-token"
    assert body["dialogId"] == "chat3129"
    assert "Connection timeout" in body["fields"]["message"]
    assert body["fields"]["attach"][1]["GRID"]
    assert "bot-token" not in caplog.text  # secret nunca logado


@pytest.mark.asyncio
async def test_bitrix_send_webhook_mode_without_bot_credentials() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"result": 1})

    provider = BitrixNotificationProvider(
        client_factory=lambda _t: httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )
    r = await provider.send(_msg(), _bitrix_target(bot=False), timeout_s=5)
    assert r.ok is True
    body = seen["body"]
    assert isinstance(body, dict)
    assert body["DIALOG_ID"] == "chat3129"
    assert "botId" not in body and "botToken" not in body


@pytest.mark.asyncio
async def test_bitrix_send_surfaces_api_error_body() -> None:
    def handler(_r: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"error": "BOT_ID_ERROR", "error_description": "Bot not found"}
        )

    provider = BitrixNotificationProvider(
        client_factory=lambda _t: httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )
    r = await provider.send(_msg(), _bitrix_target(), timeout_s=5)
    assert r.ok is False and "Bot not found" in (r.error or "")


@pytest.mark.asyncio
async def test_bitrix_send_reports_http_error_body() -> None:
    def handler(_r: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="Not Found")

    provider = BitrixNotificationProvider(
        client_factory=lambda _t: httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )
    r = await provider.send(_msg(), _bitrix_target(), timeout_s=5)
    assert r.ok is False and "404" in (r.error or "")


# ── crypto / máscara ─────────────────────────────────────────────────────
def test_secret_cipher_roundtrip() -> None:
    from nbplatform.core.crypto import SecretCipher

    c = SecretCipher(KEY)
    assert c.decrypt(c.encrypt("top-secret")) == "top-secret"


def test_provider_type_enum_values() -> None:
    assert NotificationProviderType.EMAIL == "EMAIL"
    assert NotificationProviderType.BITRIX == "BITRIX"
