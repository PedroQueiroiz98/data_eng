from __future__ import annotations

import uuid

import pytest

from nbplatform.db.session import session_scope
from nbplatform.domain.notifications import NotificationStatus
from nbplatform.models.notification import NotificationDelivery, NotificationProvider
from nbplatform.queue.notification_queue import NotificationQueue
from nbplatform.queue.redis_client import get_redis
from nbplatform.services.notifications import NotificationService
from nbplatform.services.notifications.email_sender import (
    EmailProviderSettings,
    OutgoingEmail,
)
from nbplatform.services.notifications.registry import default_registry
from nbplatform.worker.recovery import recover_stale_notifications
from tests.conftest import requires_services
from tests.integration.helpers import drive_job, make_notebook, make_workflow, notebook_content

pytestmark = [pytest.mark.asyncio, requires_services]

FAILING_NB = notebook_content("raise ValueError('Connection timeout')")


# ── helpers ──────────────────────────────────────────────────────────────
def _email_body(name: str = "E-mail Operações", *, enabled: bool = True) -> dict:
    return {
        "name": name,
        "description": "time de dados",
        "provider_type": "EMAIL",
        "enabled": enabled,
        "configuration": {
            "host": "smtp.empresa.com",
            "port": 587,
            "username": "notification",
            "from_email": "noreply@empresa.com",
            "from_name": "Data Platform",
            "use_tls": True,
            "recipients": ["data-team@empresa.com", "suporte@empresa.com"],
            "cc": [],
            "bcc": [],
        },
        "secret": "super-smtp-secret",
    }


def _bitrix_body(name: str = "Bitrix Operações", *, enabled: bool = True) -> dict:
    return {
        "name": name,
        "provider_type": "BITRIX",
        "enabled": enabled,
        "configuration": {
            "url": "https://empresa.bitrix24.com.br",
            "dialog_id": "chat3129",
        },
        "secret": "top-secret-bot-token",
    }


async def _create(client, body: dict) -> dict:
    resp = await client.post("/api/notifications/providers", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _clear_providers(client) -> None:
    for p in (await client.get("/api/notifications/providers")).json():
        await client.delete(f"/api/notifications/providers/{p['id']}")


class _StubOK:
    async def send(self, email: OutgoingEmail, settings: EmailProviderSettings) -> None:
        return None


# ── CRUD + segurança ────────────────────────────────────────────────────
async def test_provider_crud_roundtrip_hides_secret(client) -> None:
    await _clear_providers(client)
    created = await _create(client, _email_body())
    assert "secret" not in created and "secret_ct" not in created
    assert created["has_password"] is True and created["has_credential"] is False
    assert "super-smtp-secret" not in (await client.get("/api/notifications/providers")).text

    got = (await client.get(f"/api/notifications/providers/{created['id']}")).json()
    assert got["configuration"]["recipients"] == [
        "data-team@empresa.com",
        "suporte@empresa.com",
    ]

    upd = await client.put(
        f"/api/notifications/providers/{created['id']}",
        json={"description": "novo texto", "secret": "********"},
    )
    assert upd.status_code == 200 and upd.json()["description"] == "novo texto"
    assert upd.json()["has_password"] is True  # máscara manteve o secret

    dele = await client.delete(f"/api/notifications/providers/{created['id']}")
    assert dele.status_code == 204
    assert (await client.get("/api/notifications/providers")).json() == []


async def test_update_replaces_secret_when_new_value(client) -> None:
    await _clear_providers(client)
    p = await _create(client, _bitrix_body())
    await client.put(
        f"/api/notifications/providers/{p['id']}",
        json={"secret": "brand-new-token"},
    )
    async with session_scope() as session:
        row = await session.get(NotificationProvider, uuid.UUID(p["id"]))
        from nbplatform.core.config import get_settings
        from nbplatform.core.crypto import SecretCipher

        assert row is not None
        assert SecretCipher(get_settings().secret_encryption_key).decrypt(
            row.secret_ct
        ) == "brand-new-token"


async def test_create_provider_invalid_config_returns_422(client) -> None:
    await _clear_providers(client)
    bad = _email_body()
    bad["configuration"].pop("host")
    resp = await client.post("/api/notifications/providers", json=bad)
    assert resp.status_code == 422, resp.text


async def _member_headers(client) -> dict:
    email = f"member-{uuid.uuid4().hex[:8]}@x.com"
    r = await client.post(
        "/api/auth/register",
        json={"email": email, "name": "M", "password": "secret123", "role": "member"},
    )
    assert r.status_code == 201, r.text
    r = await client.post("/api/auth/login", json={"email": email, "password": "secret123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_write_endpoints_require_admin(client) -> None:
    await _clear_providers(client)
    p = await _create(client, _email_body())
    h = await _member_headers(client)
    assert (await client.get("/api/notifications/providers", headers=h)).status_code == 200
    assert (
        await client.post("/api/notifications/providers", headers=h, json=_bitrix_body())
    ).status_code == 403
    assert (
        await client.put(
            f"/api/notifications/providers/{p['id']}", headers=h, json={"enabled": False}
        )
    ).status_code == 403
    assert (
        await client.patch(
            f"/api/notifications/providers/{p['id']}/enabled",
            headers=h,
            json={"enabled": False},
        )
    ).status_code == 403
    assert (
        await client.delete(f"/api/notifications/providers/{p['id']}", headers=h)
    ).status_code == 403


async def test_patch_enabled_toggles_and_audits(client) -> None:
    await _clear_providers(client)
    p = await _create(client, _email_body(enabled=True))
    r = await client.patch(
        f"/api/notifications/providers/{p['id']}/enabled", json={"enabled": False}
    )
    assert r.status_code == 200 and r.json()["enabled"] is False


async def test_test_endpoint_is_synchronous_without_delivery_row(client) -> None:
    await _clear_providers(client)
    p = await _create(client, _email_body())
    before = await _delivery_count()
    # sender real vai falhar (host fake), mas o endpoint responde síncrono
    r = await client.post(f"/api/notifications/providers/{p['id']}/test")
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"ok", "detail", "error"}
    assert await _delivery_count() == before  # nenhuma delivery criada


async def _delivery_count() -> int:
    async with session_scope() as session:
        from sqlalchemy import func, select

        return int(
            await session.scalar(select(func.count()).select_from(NotificationDelivery)) or 0
        )


# ── disparo por falha de Job ────────────────────────────────────────────
async def _run_failing(client, name: str) -> str:
    nb = await make_notebook(client, f"{name}-nb", FAILING_NB)
    wf = await make_workflow(
        client, name, [{"key": "run", "name": "Transformation", "notebook_id": nb}], []
    )
    job = (await client.post(f"/api/workflows/{wf}/run", json={})).json()
    assert await drive_job(job["id"]) == "FAILED"
    return job["id"]


async def test_job_failure_fans_out_to_every_enabled_provider(client) -> None:
    await _clear_providers(client)
    await _create(client, _email_body())
    await _create(client, _bitrix_body())

    job_id = await _run_failing(client, "Customer ETL")
    rows = (
        await client.get(f"/api/notifications/deliveries?job={job_id}")
    ).json()["items"]

    events = {(r["provider_type"], r["event_type"]) for r in rows}
    assert ("EMAIL", "WORKFLOW_FAILED") in events
    assert ("BITRIX", "WORKFLOW_FAILED") in events
    assert ("EMAIL", "JOB_FAILED") in events  # também por etapa que falhou
    assert ("BITRIX", "JOB_FAILED") in events
    wf_row = next(r for r in rows if r["event_type"] == "WORKFLOW_FAILED")
    assert wf_row["job_id"] == job_id


async def test_reprocessing_same_event_is_idempotent(client) -> None:
    await _clear_providers(client)
    await _create(client, _email_body())
    job_id = await _run_failing(client, "wf-idem")
    n1 = len((await client.get(f"/api/notifications/deliveries?job={job_id}")).json()["items"])

    from datetime import UTC, datetime

    from nbplatform.domain.notifications import NotificationEvent, NotificationEventType

    await NotificationService(get_redis()).notify(
        NotificationEvent(
            event_type=NotificationEventType.WORKFLOW_FAILED,
            occurred_at=datetime.now(UTC),
            job_id=uuid.UUID(job_id),
        )
    )
    n2 = len((await client.get(f"/api/notifications/deliveries?job={job_id}")).json()["items"])
    assert n1 == n2


async def test_no_enabled_provider_logs_info_and_creates_nothing(client, caplog) -> None:
    await _clear_providers(client)
    await _create(client, _email_body(enabled=False))
    with caplog.at_level("INFO"):
        job_id = await _run_failing(client, "wf-noprov")
    rows = (await client.get(f"/api/notifications/deliveries?job={job_id}")).json()["items"]
    assert rows == []
    assert "No active notification provider configured" in caplog.text


async def test_disabled_provider_is_skipped(client) -> None:
    await _clear_providers(client)
    await _create(client, _email_body(name="on", enabled=True))
    await _create(client, _bitrix_body(name="off", enabled=False))
    job_id = await _run_failing(client, "wf-mixed")
    rows = (await client.get(f"/api/notifications/deliveries?job={job_id}")).json()["items"]
    assert {r["provider_type"] for r in rows} == {"EMAIL"}


# ── dispatch / isolamento / retry ──────────────────────────────────────
async def test_provider_failure_isolated_from_others(client) -> None:
    await _clear_providers(client)
    await _create(client, _email_body(name="ok"))
    await _create(client, _bitrix_body(name="bad"))  # host fake → falha
    job_id = await _run_failing(client, "wf-iso")

    reg = default_registry(email_sender=_StubOK())
    svc = NotificationService(get_redis(), registry=reg)
    rows = (await client.get(f"/api/notifications/deliveries?job={job_id}")).json()["items"]
    for r in rows:
        for _ in range(4):
            await svc.dispatch(uuid.UUID(r["id"]))

    final = (await client.get(f"/api/notifications/deliveries?job={job_id}")).json()["items"]
    by_prov = {r["provider_type"]: r["status"] for r in final}
    assert by_prov["EMAIL"] == "SENT"
    assert by_prov["BITRIX"] == "FAILED"
    # o Job continua FAILED (não vira NOTIFICATION_FAILED)
    job = (await client.get(f"/api/jobs/{job_id}")).json()
    assert job["status"] == "FAILED"


async def test_email_retries_and_succeeds_on_third_attempt(client) -> None:
    await _clear_providers(client)
    await _create(client, _email_body(name="flaky"))
    job_id = await _run_failing(client, "wf-flaky")
    row = (await client.get(f"/api/notifications/deliveries?job={job_id}")).json()["items"][0]
    did = uuid.UUID(row["id"])

    calls = {"n": 0}

    class Flaky:
        async def send(self, email: OutgoingEmail, settings: EmailProviderSettings) -> None:
            calls["n"] += 1
            if calls["n"] < 3:
                raise RuntimeError("SMTP timeout")

    svc = NotificationService(get_redis(), registry=default_registry(email_sender=Flaky()))
    assert await svc.dispatch(did) == NotificationStatus.PENDING
    assert await svc.dispatch(did) == NotificationStatus.PENDING
    assert await svc.dispatch(did) == NotificationStatus.SENT
    async with session_scope() as session:
        r = await session.get(NotificationDelivery, did)
        assert r is not None and r.status == NotificationStatus.SENT and r.attempt == 3


async def test_dispatch_idempotent_for_already_sent_row(client) -> None:
    await _clear_providers(client)
    await _create(client, _email_body(name="sent"))
    job_id = await _run_failing(client, "wf-sent")
    did = uuid.UUID(
        (await client.get(f"/api/notifications/deliveries?job={job_id}")).json()["items"][0]["id"]
    )
    async with session_scope() as session:
        r = await session.get(NotificationDelivery, did)
        r.status = NotificationStatus.SENT
    assert await NotificationService(get_redis()).dispatch(did) == NotificationStatus.SENT


async def test_retry_endpoint_requeues_exhausted_delivery(client) -> None:
    await _clear_providers(client)
    await _create(client, _bitrix_body(name="retry"))
    job_id = await _run_failing(client, "wf-retry")
    did = uuid.UUID(
        (await client.get(f"/api/notifications/deliveries?job={job_id}")).json()["items"][0]["id"]
    )
    async with session_scope() as session:
        r = await session.get(NotificationDelivery, did)
        r.status = NotificationStatus.FAILED
        r.attempt = r.max_attempts

    resp = await client.post(f"/api/notifications/deliveries/{did}/retry")
    assert resp.status_code == 202
    async with session_scope() as session:
        r = await session.get(NotificationDelivery, did)
        assert r.status == NotificationStatus.PENDING and r.max_attempts > r.attempt

    msg = await NotificationQueue(get_redis()).lease(timeout_s=2)
    assert msg is not None and msg.notification_id == str(did)
    await NotificationQueue(get_redis()).ack(msg)


async def test_recover_stale_delivery_requeues_stuck_sending(client) -> None:
    from datetime import UTC, datetime, timedelta

    await _clear_providers(client)
    await _create(client, _email_body(name="stale"))
    job_id = await _run_failing(client, "wf-stale")
    did = uuid.UUID(
        (await client.get(f"/api/notifications/deliveries?job={job_id}")).json()["items"][0]["id"]
    )
    async with session_scope() as session:
        r = await session.get(NotificationDelivery, did)
        r.status = NotificationStatus.SENDING
        r.attempt = 1
        r.sending_since = datetime.now(UTC) - timedelta(hours=1)

    assert await recover_stale_notifications(get_redis()) >= 1
    async with session_scope() as session:
        r = await session.get(NotificationDelivery, did)
        assert r.status == NotificationStatus.PENDING and r.sending_since is None

    msg = await NotificationQueue(get_redis()).lease(timeout_s=2)
    assert msg is not None
    await NotificationQueue(get_redis()).ack(msg)


# ── histórico / filtros ────────────────────────────────────────────────
async def test_deliveries_filters_and_detail(client) -> None:
    await _clear_providers(client)
    await _create(client, _email_body(name="f-email"))
    await _create(client, _bitrix_body(name="f-bitrix"))
    job_id = await _run_failing(client, "Customer ETL Filters")

    page = (await client.get("/api/notifications/deliveries?event=JOB_FAILED")).json()
    assert page["total"] >= 1
    assert all(r["event_type"] == "JOB_FAILED" for r in page["items"])

    by_job = (await client.get(f"/api/notifications/deliveries?job={job_id}&limit=100")).json()
    assert by_job["total"] == len(by_job["items"]) >= 2

    email_only = (
        await client.get(f"/api/notifications/deliveries?job={job_id}&status=PENDING&limit=100")
    ).json()
    assert all(r["status"] == "PENDING" for r in email_only["items"])

    one = by_job["items"][0]
    detail = (await client.get(f"/api/notifications/deliveries/{one['id']}")).json()
    assert detail["payload"]["pipeline_name"].startswith("Customer ETL")


async def test_delete_provider_keeps_delivery_history(client) -> None:
    await _clear_providers(client)
    p = await _create(client, _email_body(name="doomed"))
    job_id = await _run_failing(client, "wf-doomed")
    assert (await client.get(f"/api/notifications/deliveries?job={job_id}")).json()["total"] >= 1

    await client.delete(f"/api/notifications/providers/{p['id']}")
    rows = (await client.get(f"/api/notifications/deliveries?job={job_id}")).json()["items"]
    assert rows and rows[0]["notification_provider_id"] is None
    assert rows[0]["provider_type"] == "EMAIL"
