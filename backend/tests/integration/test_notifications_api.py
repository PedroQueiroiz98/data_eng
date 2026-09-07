from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from nbplatform.db.session import session_scope
from nbplatform.domain.notifications import NotificationEvent, NotificationStatus
from nbplatform.models.notification import Notification
from nbplatform.queue.notification_queue import NotificationQueue
from nbplatform.queue.redis_client import get_redis
from nbplatform.services.notifications import NotificationService
from nbplatform.services.notifications.email_sender import OutgoingEmail
from nbplatform.services.notifications.resolved_settings import EmailProviderSettings
from nbplatform.worker.recovery import recover_stale_notifications
from tests.conftest import requires_services
from tests.integration.helpers import drive_job, make_notebook, make_workflow, notebook_content

pytestmark = [pytest.mark.asyncio, requires_services]

FAILING_NB = notebook_content("raise ValueError('invalid date format')")


async def _configure(client, workflow_id: str) -> None:
    resp = await client.put(
        f"/api/workflows/{workflow_id}/notifications",
        json={
            "on_failure": True,
            "email_enabled": True,
            "email_recipients": ["pedro@empresa.com", "suporte@empresa.com"],
            "email_cc": ["devops@empresa.com"],
            "bitrix_enabled": True,
            "bitrix_dialog_id": "chat3129",
        },
    )
    assert resp.status_code == 200, resp.text


async def test_config_roundtrip_and_defaults(client) -> None:
    nb = await make_notebook(client, "n", notebook_content("print(1)"))
    wf = await make_workflow(client, "wf", [{"key": "a", "name": "A", "notebook_id": nb}], [])

    got = (await client.get(f"/api/workflows/{wf}/notifications")).json()
    assert got["on_failure"] is True and got["email_enabled"] is False

    await _configure(client, wf)
    got = (await client.get(f"/api/workflows/{wf}/notifications")).json()
    assert got["email_recipients"] == ["pedro@empresa.com", "suporte@empresa.com"]
    assert got["bitrix_dialog_id"] == "chat3129"


async def test_global_settings_never_returns_secrets(client) -> None:
    resp = await client.put(
        "/api/notifications/settings",
        json={
            "email_enabled": True,
            "smtp_host": "smtp.local",
            "smtp_port": 587,
            "smtp_from": "ci@x.com",
            "smtp_password": "super-smtp-secret",
            "bitrix_enabled": True,
            "bitrix_url": "https://b24.example",
            "bitrix_bot_id": "42",
            "bitrix_bot_token": "top-secret-bot-token",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["smtp_password_masked"] == "********"
    assert body["bitrix_bot_token_masked"] == "********"
    assert "super-smtp-secret" not in resp.text
    assert "top-secret-bot-token" not in resp.text

    # editar sem mexer no secret mantém o valor (envia a máscara de volta)
    resp = await client.put(
        "/api/notifications/settings",
        json={
            "email_enabled": True,
            "smtp_host": "smtp2.local",
            "smtp_from": "ci@x.com",
            "smtp_password": "********",
            "bitrix_enabled": True,
            "bitrix_url": "https://b24.example",
            "bitrix_bot_id": "42",
            "bitrix_bot_token": "********",
        },
    )
    assert resp.json()["bitrix_bot_token_masked"] == "********"


async def test_job_failure_creates_notification_history_idempotently(client) -> None:
    nb = await make_notebook(client, "failnb", FAILING_NB)
    wf = await make_workflow(
        client, "Customer ETL", [{"key": "run", "name": "Execute Notebook", "notebook_id": nb}], []
    )
    await _configure(client, wf)

    job = (await client.post(f"/api/workflows/{wf}/run", json={})).json()
    status = await drive_job(job["id"])
    assert status == "FAILED"

    rows = (await client.get(f"/api/jobs/{job['id']}/notifications")).json()
    assert {r["channel"] for r in rows} == {"EMAIL", "BITRIX"}
    assert all(r["event_type"] == "JOB_FAILED" for r in rows)
    email_row = next(r for r in rows if r["channel"] == "EMAIL")
    assert "pedro@empresa.com" in (email_row["recipient"] or "")

    # reprocessar o mesmo evento não duplica (idempotência §13)
    await NotificationService(get_redis()).enqueue_job_event(
        uuid.UUID(job["id"]), NotificationEvent.JOB_FAILED
    )
    rows2 = (await client.get(f"/api/jobs/{job['id']}/notifications")).json()
    assert len(rows2) == len(rows) == 2


async def test_no_config_does_not_create_notifications(client) -> None:
    nb = await make_notebook(client, "failnb2", FAILING_NB)
    wf = await make_workflow(
        client, "wf2", [{"key": "run", "name": "R", "notebook_id": nb}], []
    )
    job = (await client.post(f"/api/workflows/{wf}/run", json={})).json()
    status = await drive_job(job["id"])
    assert status == "FAILED"

    rows = (await client.get(f"/api/jobs/{job['id']}/notifications")).json()
    assert rows == []


async def test_global_default_on_failure_notifies_pipelines_without_config(client) -> None:
    base = {
        "email_enabled": True,
        "smtp_host": "smtp.local",
        "smtp_from": "ci@x.com",
        "smtp_password": "********",
        "bitrix_enabled": False,
    }
    try:
        r = await client.put(
            "/api/notifications/settings",
            json={
                **base,
                "default_on_failure": True,
                "default_email_recipients": ["oncall@empresa.com"],
            },
        )
        assert r.status_code == 200, r.text
        assert r.json()["default_on_failure"] is True

        nb = await make_notebook(client, "failnb3", FAILING_NB)
        wf = await make_workflow(
            client, "wf-sem-config", [{"key": "run", "name": "R", "notebook_id": nb}], []
        )
        job = (await client.post(f"/api/workflows/{wf}/run", json={})).json()
        assert await drive_job(job["id"]) == "FAILED"

        rows = (await client.get(f"/api/jobs/{job['id']}/notifications")).json()
        assert [r["channel"] for r in rows] == ["EMAIL"]
        assert rows[0]["event_type"] == "JOB_FAILED"
        assert "oncall@empresa.com" in (rows[0]["recipient"] or "")
    finally:
        await client.put(
            "/api/notifications/settings",
            json={**base, "default_on_failure": False, "default_email_recipients": []},
        )


# ── segurança: endpoints admin ────────────────────────────────────────────────
async def _member_token(client) -> str:
    email = f"member-{uuid.uuid4().hex[:8]}@x.com"
    r = await client.post(
        "/api/auth/register",
        json={"email": email, "name": "Member", "password": "secret123", "role": "member"},
    )
    assert r.status_code == 201, r.text
    r = await client.post("/api/auth/login", json={"email": email, "password": "secret123"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


async def test_global_settings_endpoints_require_admin(client) -> None:
    headers = {"Authorization": f"Bearer {await _member_token(client)}"}
    assert (
        await client.get("/api/notifications/settings", headers=headers)
    ).status_code == 403
    assert (
        await client.put(
            "/api/notifications/settings", headers=headers, json={"email_enabled": False}
        )
    ).status_code == 403


# ── retry manual (§15 / cenário 6) ───────────────────────────────────────────
async def _failed_job_with_rows(client, name: str) -> tuple[str, list[dict]]:
    nb = await make_notebook(client, f"{name}-nb", FAILING_NB)
    wf = await make_workflow(
        client, name, [{"key": "run", "name": "R", "notebook_id": nb}], []
    )
    await _configure(client, wf)
    job = (await client.post(f"/api/workflows/{wf}/run", json={})).json()
    assert await drive_job(job["id"]) == "FAILED"
    rows = (await client.get(f"/api/jobs/{job['id']}/notifications")).json()
    return job["id"], rows


async def test_retry_endpoint_requeues_exhausted_notification(client) -> None:
    _job, rows = await _failed_job_with_rows(client, "wf-retry")
    target = uuid.UUID(next(r for r in rows if r["channel"] == "BITRIX")["id"])

    async with session_scope() as session:
        row = await session.get(Notification, target)
        assert row is not None
        row.status = NotificationStatus.FAILED
        row.attempt = row.max_attempts  # esgotada

    resp = await client.post(f"/api/notifications/{target}/retry")
    assert resp.status_code == 202

    async with session_scope() as session:
        row = await session.get(Notification, target)
        assert row is not None
        assert row.status == NotificationStatus.PENDING
        assert row.next_retry_at is None
        assert row.max_attempts > row.attempt  # ganhou +1 tentativa

    msg = await NotificationQueue(get_redis()).lease(timeout_s=2)
    assert msg is not None and msg.notification_id == str(target)
    await NotificationQueue(get_redis()).ack(msg)


async def test_dispatch_is_idempotent_for_already_sent_row(client) -> None:
    _job, rows = await _failed_job_with_rows(client, "wf-idem")
    target = uuid.UUID(rows[0]["id"])
    async with session_scope() as session:
        row = await session.get(Notification, target)
        assert row is not None
        row.status = NotificationStatus.SENT

    result = await NotificationService(get_redis()).dispatch(target)
    assert result == NotificationStatus.SENT


async def test_email_notification_retries_and_succeeds_on_third_attempt(client) -> None:
    await client.put(
        "/api/notifications/settings",
        json={
            "email_enabled": True,
            "smtp_host": "smtp.local",
            "smtp_from": "ci@x.com",
            "smtp_password": "********",
            "bitrix_enabled": False,
        },
    )
    nb = await make_notebook(client, "wf-r6-nb", FAILING_NB)
    wf = await make_workflow(
        client, "wf-r6", [{"key": "run", "name": "R", "notebook_id": nb}], []
    )
    await client.put(
        f"/api/workflows/{wf}/notifications",
        json={
            "on_failure": True,
            "email_enabled": True,
            "email_recipients": ["oncall@empresa.com"],
            "bitrix_enabled": False,
        },
    )
    job = (await client.post(f"/api/workflows/{wf}/run", json={})).json()
    assert await drive_job(job["id"]) == "FAILED"
    rows = (await client.get(f"/api/jobs/{job['id']}/notifications")).json()
    assert [r["channel"] for r in rows] == ["EMAIL"]
    nid = uuid.UUID(rows[0]["id"])

    calls = {"n": 0}

    class FlakySender:
        async def send(self, email: OutgoingEmail, settings: EmailProviderSettings) -> None:
            calls["n"] += 1
            if calls["n"] < 3:
                raise RuntimeError("SMTP timeout")

    service = NotificationService(get_redis(), email_sender=FlakySender())
    assert await service.dispatch(nid) == NotificationStatus.PENDING
    assert await service.dispatch(nid) == NotificationStatus.PENDING
    assert await service.dispatch(nid) == NotificationStatus.SENT

    async with session_scope() as session:
        row = await session.get(Notification, nid)
        assert row is not None
        assert row.status == NotificationStatus.SENT
        assert row.attempt == 3
        assert row.sent_at is not None
        assert row.sending_since is None


# ── recovery de notificações abandonadas (worker morto) ──────────────────────
async def test_recover_stale_notifications_requeues_stuck_sending(client) -> None:
    _job, rows = await _failed_job_with_rows(client, "wf-stale")
    target = uuid.UUID(rows[0]["id"])
    async with session_scope() as session:
        row = await session.get(Notification, target)
        assert row is not None
        row.status = NotificationStatus.SENDING
        row.attempt = 1
        row.sending_since = datetime.now(UTC) - timedelta(hours=1)

    recovered = await recover_stale_notifications(get_redis())
    assert recovered >= 1

    async with session_scope() as session:
        row = await session.get(Notification, target)
        assert row is not None
        assert row.status == NotificationStatus.PENDING
        assert row.sending_since is None

    msg = await NotificationQueue(get_redis()).lease(timeout_s=2)
    assert msg is not None and msg.notification_id == str(target)
    await NotificationQueue(get_redis()).ack(msg)


async def test_reclaim_processing_moves_orphans_back_to_main_queue(client) -> None:
    queue = NotificationQueue(get_redis())
    orphan = str(uuid.uuid4())
    await get_redis().lpush(
        queue.settings.redis_queue_notifications_processing, orphan
    )

    moved = await queue.reclaim_processing()
    assert moved >= 1

    msg = await queue.lease(timeout_s=2)
    assert msg is not None and msg.notification_id == orphan
    await queue.ack(msg)
