"""ACL por Workspace (workspace_members) — Fase 1."""

from __future__ import annotations

import uuid

import pytest

from tests.conftest import requires_services

pytestmark = [pytest.mark.asyncio, requires_services]


async def _member(client, role_hint: str = "m") -> tuple[str, str]:
    """Registra um usuário 'member' e devolve (user_id, bearer_token)."""
    email = f"{role_hint}-{uuid.uuid4().hex[:8]}@x.com"
    r = await client.post(
        "/api/auth/register",
        json={"email": email, "name": "M", "password": "secret123", "role": "member"},
    )
    assert r.status_code == 201, r.text
    uid = r.json()["id"]
    r = await client.post("/api/auth/login", json={"email": email, "password": "secret123"})
    assert r.status_code == 200, r.text
    return uid, r.json()["access_token"]


async def _new_workspace(client, name: str) -> str:
    r = await client.post("/api/workspaces", json={"name": name})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def test_non_member_gets_403_and_scoped_list(client) -> None:
    wid = await _new_workspace(client, "acl-a")
    _uid, token = await _member(client)
    h = {"Authorization": f"Bearer {token}"}

    assert (await client.get(f"/api/workspaces/{wid}", headers=h)).status_code == 403
    assert (
        await client.get(f"/api/workspaces/{wid}/tree", headers=h)
    ).status_code == 403
    # a listagem some para quem não é membro
    listed = (await client.get("/api/workspaces", headers=h)).json()
    assert all(w["id"] != wid for w in listed)


async def test_viewer_can_read_but_not_write_then_editor_can(client) -> None:
    wid = await _new_workspace(client, "acl-b")
    uid, token = await _member(client)
    h = {"Authorization": f"Bearer {token}"}

    # owner (admin) adiciona como VIEWER
    r = await client.put(
        f"/api/workspaces/{wid}/members/{uid}", json={"role": "VIEWER"}
    )
    assert r.status_code == 200, r.text

    assert (await client.get(f"/api/workspaces/{wid}/tree", headers=h)).status_code == 200
    w = await client.put(
        f"/api/workspaces/{wid}/file?path=notebooks/x.py",
        headers=h,
        json={"text": "print(1)\n"},
    )
    assert w.status_code == 403

    # promove a EDITOR → agora escreve
    r = await client.put(
        f"/api/workspaces/{wid}/members/{uid}", json={"role": "EDITOR"}
    )
    assert r.status_code == 200
    w = await client.put(
        f"/api/workspaces/{wid}/file?path=notebooks/x.py",
        headers=h,
        json={"text": "print(1)\n"},
    )
    assert w.status_code == 200, w.text
    # e aparece na listagem dele
    listed = (await client.get("/api/workspaces", headers=h)).json()
    assert any(x["id"] == wid for x in listed)


async def test_only_owner_manages_members(client) -> None:
    wid = await _new_workspace(client, "acl-c")
    editor_uid, editor_tok = await _member(client, "ed")
    other_uid, _ = await _member(client, "ot")
    await client.put(
        f"/api/workspaces/{wid}/members/{editor_uid}", json={"role": "EDITOR"}
    )
    h = {"Authorization": f"Bearer {editor_tok}"}
    # editor não pode adicionar membros
    r = await client.put(
        f"/api/workspaces/{wid}/members/{other_uid}", json={"role": "VIEWER"}, headers=h
    )
    assert r.status_code == 403


async def test_cannot_remove_or_demote_last_owner(client) -> None:
    wid = await _new_workspace(client, "acl-d")
    # descobre o owner (o admin que criou)
    members = (await client.get(f"/api/workspaces/{wid}/members")).json()
    owners = [m for m in members if m["role"] == "OWNER"]
    assert len(owners) == 1
    owner_uid = owners[0]["user_id"]

    r = await client.delete(f"/api/workspaces/{wid}/members/{owner_uid}")
    assert r.status_code == 422
    r = await client.put(
        f"/api/workspaces/{wid}/members/{owner_uid}", json={"role": "EDITOR"}
    )
    assert r.status_code == 422


async def test_owner_can_patch_and_delete_workspace(client) -> None:
    wid = await _new_workspace(client, "acl-e")
    uid, token = await _member(client)
    h = {"Authorization": f"Bearer {token}"}
    await client.put(f"/api/workspaces/{wid}/members/{uid}", json={"role": "EDITOR"})
    # editor não edita o Workspace
    assert (
        await client.patch(f"/api/workspaces/{wid}", json={"name": "x"}, headers=h)
    ).status_code == 403
    await client.put(f"/api/workspaces/{wid}/members/{uid}", json={"role": "OWNER"})
    assert (
        await client.patch(f"/api/workspaces/{wid}", json={"name": "acl-e2"}, headers=h)
    ).status_code == 200
