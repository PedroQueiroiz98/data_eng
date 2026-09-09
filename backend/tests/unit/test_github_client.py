from __future__ import annotations

import httpx
import pytest

from nbplatform.core.errors import DomainValidationError
from nbplatform.services.github import client as gh_client


def _mock_client(handle):  # type: ignore[no-untyped-def]
    def make() -> httpx.AsyncClient:
        return httpx.AsyncClient(
            transport=httpx.MockTransport(handle), base_url="https://api.github.com"
        )

    return make


async def test_get_authenticated_user_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer tok123"
        return httpx.Response(
            200,
            json={
                "id": 42,
                "login": "octocat",
                "name": "Octo Cat",
                "email": "octo@example.com",
                "avatar_url": "https://avatars/octo.png",
            },
        )

    monkeypatch.setattr(gh_client, "_make_client", _mock_client(handle))
    user = await gh_client.get_authenticated_user("tok123")
    assert user.id == 42
    assert user.login == "octocat"
    assert user.email == "octo@example.com"


async def test_get_authenticated_user_falls_back_to_primary_email(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/user":
            return httpx.Response(
                200,
                json={
                    "id": 1,
                    "login": "priv",
                    "name": None,
                    "email": None,
                    "avatar_url": None,
                },
            )
        assert request.url.path == "/user/emails"
        return httpx.Response(
            200,
            json=[
                {"email": "secondary@example.com", "primary": False},
                {"email": "primary@example.com", "primary": True},
            ],
        )

    monkeypatch.setattr(gh_client, "_make_client", _mock_client(handle))
    user = await gh_client.get_authenticated_user("tok123")
    assert user.email == "primary@example.com"


async def test_get_authenticated_user_invalid_token(monkeypatch: pytest.MonkeyPatch) -> None:
    def handle(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "Bad credentials"})

    monkeypatch.setattr(gh_client, "_make_client", _mock_client(handle))
    with pytest.raises(DomainValidationError):
        await gh_client.get_authenticated_user("bad-token")


async def test_list_repos_paginates_until_short_page(monkeypatch: pytest.MonkeyPatch) -> None:
    def repo(name: str) -> dict[str, object]:
        return {
            "full_name": f"octocat/{name}",
            "private": False,
            "default_branch": "main",
            "clone_url": f"https://github.com/octocat/{name}.git",
            "updated_at": "2026-01-01T00:00:00Z",
        }

    def handle(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params.get("page", "1"))
        if page == 1:
            return httpx.Response(200, json=[repo("a")] * 100)
        return httpx.Response(200, json=[repo("b")])

    monkeypatch.setattr(gh_client, "_make_client", _mock_client(handle))
    repos = await gh_client.list_repos("tok123")
    assert len(repos) == 101


async def test_list_branches_repo_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    def handle(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"message": "Not Found"})

    monkeypatch.setattr(gh_client, "_make_client", _mock_client(handle))
    with pytest.raises(DomainValidationError):
        await gh_client.list_branches("tok123", "octocat/ghost")
