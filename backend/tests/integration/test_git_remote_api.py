"""Wiring das rotas `/api/workspace/git/{remote,push,pull,merge/abort}` com a
conta GitHub. A lógica de push/pull/conflito em si já é coberta contra um bare
repo local em `tests/unit/test_git_service_remote.py` — aqui só garante que a
rota exige uma conta GitHub conectada antes de tentar qualquer coisa.
"""

from __future__ import annotations

import httpx

from tests.conftest import requires_services

pytestmark = requires_services


async def test_remote_link_requires_github_connected(client: httpx.AsyncClient) -> None:
    await client.delete("/api/github/auth")
    r = await client.post(
        "/api/workspace/git/remote",
        json={"repo_full_name": "octocat/hello-world", "branch": "main", "base_dir": ""},
    )
    assert r.status_code == 422, r.text


async def test_push_requires_github_connected(client: httpx.AsyncClient) -> None:
    await client.delete("/api/github/auth")
    r = await client.post("/api/workspace/git/push")
    assert r.status_code == 422, r.text


async def test_pull_requires_github_connected(client: httpx.AsyncClient) -> None:
    await client.delete("/api/github/auth")
    r = await client.post("/api/workspace/git/pull")
    assert r.status_code == 422, r.text
