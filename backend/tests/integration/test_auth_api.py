from __future__ import annotations

import uuid

import httpx
import pytest

from nbplatform.api.main import create_app
from nbplatform.core.config import get_settings
from tests.conftest import requires_services

pytestmark = [pytest.mark.asyncio, requires_services]


@pytest.fixture
async def anon_client():
    app = create_app()
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as ac,
    ):
        yield ac


async def test_login_success_and_me(anon_client) -> None:
    s = get_settings()
    resp = await anon_client.post(
        "/api/auth/login", json={"email": s.admin_email, "password": s.admin_password}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["role"] == "admin"

    me = await anon_client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"}
    )
    assert me.status_code == 200
    assert me.json()["email"] == s.admin_email


async def test_login_wrong_password(anon_client) -> None:
    s = get_settings()
    resp = await anon_client.post(
        "/api/auth/login", json={"email": s.admin_email, "password": "nope"}
    )
    assert resp.status_code == 401


async def test_protected_route_requires_token(anon_client) -> None:
    resp = await anon_client.get("/api/notebooks")
    assert resp.status_code == 401


async def test_member_cannot_manage_secrets(anon_client, client) -> None:
    email = f"member-{uuid.uuid4().hex[:10]}@nbp.local"
    reg = await client.post(
        "/api/auth/register",
        json={"email": email, "name": "Member", "password": "member123", "role": "member"},
    )
    assert reg.status_code == 201

    login = await anon_client.post(
        "/api/auth/login", json={"email": email, "password": "member123"}
    )
    member_token = login.json()["access_token"]

    resp = await anon_client.get(
        "/api/secrets", headers={"Authorization": f"Bearer {member_token}"}
    )
    assert resp.status_code == 403

    # mas pode ler notebooks
    ok = await anon_client.get(
        "/api/notebooks", headers={"Authorization": f"Bearer {member_token}"}
    )
    assert ok.status_code == 200
