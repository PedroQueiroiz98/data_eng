from __future__ import annotations

import uuid

import pytest

from nbplatform.domain.notifications import NotificationEvent
from nbplatform.queue.redis_client import get_redis
from nbplatform.services.notifications import NotificationService
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
