from __future__ import annotations

from typing import Any

import httpx
import pytest

from nbplatform.services.github import client as gh_client
from tests.conftest import requires_services

pytestmark = requires_services


class _FakeUser:
    id = 999
    login = "octocat"
    name = "Octo Cat"
    email = "octo@example.com"
    avatar_url = "https://avatars/octo.png"


class _FakeRepo:
    full_name = "octocat/hello-world"
    private = False
    default_branch = "main"
    clone_url = "https://github.com/octocat/hello-world.git"
    updated_at = "2026-01-01T00:00:00Z"


class _FakeBranch:
    name = "main"


@pytest.fixture(autouse=True)
def _fake_github(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_user(token: str) -> Any:
        if token == "bad-token":
            from nbplatform.core.errors import DomainValidationError

            raise DomainValidationError("Token do GitHub inválido ou expirado.")
        return _FakeUser()

    async def fake_repos(_token: str) -> list[Any]:
        return [_FakeRepo()]

    async def fake_branches(_token: str, _repo: str) -> list[Any]:
        return [_FakeBranch()]

    monkeypatch.setattr(gh_client, "get_authenticated_user", fake_user)
    monkeypatch.setattr(gh_client, "list_repos", fake_repos)
    monkeypatch.setattr(gh_client, "list_branches", fake_branches)


@pytest.fixture(autouse=True)
async def _disconnected_start(client: httpx.AsyncClient) -> None:
    # a conta GitHub é 1:1 com o usuário (mesmo admin seedado em todo teste de
    # integração) — garante estado limpo entre testes deste arquivo.
    await client.delete("/api/github/auth")


async def test_status_before_connect_is_disconnected(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/github/status")
    assert r.status_code == 200
    assert r.json() == {
        "connected": False,
        "username": None,
        "email": None,
        "avatar_url": None,
        "repo_full_name": None,
        "repo_default_branch": None,
        "base_dir": None,
        "last_sync_at": None,
    }


async def test_connect_rejects_invalid_token(client: httpx.AsyncClient) -> None:
    r = await client.post("/api/github/auth", json={"token": "bad-token"})
    assert r.status_code == 422, r.text


async def test_connect_then_status_never_leaks_token(client: httpx.AsyncClient) -> None:
    r = await client.post("/api/github/auth", json={"token": "ghp_supersecret123"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["connected"] is True
    assert body["username"] == "octocat"
    assert body["email"] == "octo@example.com"
    assert "token" not in r.text
    assert "ghp_supersecret123" not in r.text

    status_r = await client.get("/api/github/status")
    assert status_r.json()["username"] == "octocat"
    assert "ghp_supersecret123" not in status_r.text


async def test_repos_and_branches_require_connection_first(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/github/repos")
    assert r.status_code == 422, r.text

    await client.post("/api/github/auth", json={"token": "ghp_x"})
    r2 = await client.get("/api/github/repos")
    assert r2.status_code == 200, r2.text
    assert r2.json() == [
        {
            "full_name": "octocat/hello-world",
            "private": False,
            "default_branch": "main",
            "clone_url": "https://github.com/octocat/hello-world.git",
            "updated_at": "2026-01-01T00:00:00Z",
        }
    ]

    r3 = await client.get("/api/github/repos/octocat/hello-world/branches")
    assert r3.status_code == 200, r3.text
    assert r3.json() == [{"name": "main"}]


async def test_disconnect_clears_status(client: httpx.AsyncClient) -> None:
    await client.post("/api/github/auth", json={"token": "ghp_x"})
    r = await client.delete("/api/github/auth")
    assert r.status_code == 204, r.text
    status_r = await client.get("/api/github/status")
    assert status_r.json()["connected"] is False
