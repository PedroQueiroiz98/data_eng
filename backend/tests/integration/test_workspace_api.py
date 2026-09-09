"""Workspace único (`/api/workspace/*`): File Explorer sem `:id`, raiz vazia,
integridade de referências de Workflow em rename/delete."""

from __future__ import annotations

import uuid

import pytest

from tests.conftest import requires_services

pytestmark = [pytest.mark.asyncio, requires_services]


def _p(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


async def test_no_id_in_routes_and_meta(client) -> None:
    ws = (await client.get("/api/workspace")).json()
    assert ws["slug"] == "root"
    assert ws["root_path"].endswith("/workspace")
    # rota antiga com :id não existe mais
    assert (await client.get(f"/api/workspaces/{uuid.uuid4()}/tree")).status_code == 404


async def test_provisioning_creates_no_skeleton_no_gitignore(client) -> None:
    # A raiz não é auto-populada: sem `.gitignore` e `.workspace` fica oculto.
    # (Não checamos "pasta X não existe" porque o dir é compartilhado entre testes;
    # a garantia de skeleton vazio está em test_workspace_layout.test_no_skeleton_dirs.)
    tree = (await client.get("/api/workspace/tree")).json()
    names = {c["name"] for c in (tree["children"] or [])}
    assert ".workspace" not in names
    assert (
        await client.get("/api/workspace/file", params={"path": ".gitignore"})
    ).status_code == 404


async def test_file_crud_without_id(client) -> None:
    d = _p("proj")
    assert (await client.post("/api/workspace/dir", params={"path": d})).status_code == 201
    w = await client.put(
        "/api/workspace/file", params={"path": f"{d}/a.py"}, json={"text": "x = 1\n"}
    )
    assert w.status_code == 200 and w.json()["kind"] == "text"
    got = await client.get("/api/workspace/file", params={"path": f"{d}/a.py"})
    assert got.json()["content"] == "x = 1\n"
    fp = (
        await client.get("/api/workspace/file/paths", params={"path": f"{d}/a.py"})
    ).json()
    assert fp["workspace_path"] == f"/root/{d}/a.py"
    assert (
        await client.delete("/api/workspace/file", params={"path": d, "recursive": "true"})
    ).status_code == 204


async def test_rename_propagates_to_workflow_task(client) -> None:
    d = _p("wf")
    src = f"{d}/etl.ipynb"
    dst = f"{d}/etl_renamed.ipynb"
    nb = {
        "nbformat": 4, "nbformat_minor": 5,
        "metadata": {"kernelspec": {"name": "python3", "display_name": "Python 3"}},
        "cells": [
            {"cell_type": "code", "metadata": {"tags": ["parameters"]}, "source": "",
             "outputs": [], "execution_count": None},
            {"cell_type": "code", "metadata": {}, "source": "x = 1\n",
             "outputs": [], "execution_count": None},
        ],
    }
    assert (
        await client.put("/api/workspace/file", params={"path": src}, json={"notebook": nb})
    ).status_code == 200

    wf = (await client.post("/api/workflows", json={"name": _p("ETL")})).json()
    g = await client.put(
        f"/api/workflows/{wf['id']}/graph",
        json={
            "tasks": [
                {"key": "t1", "name": "etl", "type": "NOTEBOOK",
                 "notebook_path": src, "ui_position": {"x": 0, "y": 0}}
            ],
            "dependencies": [],
        },
    )
    assert g.status_code == 200, g.text

    r = await client.post("/api/workspace/rename", json={"from": src, "to": dst})
    assert r.status_code == 200, r.text

    det = (await client.get(f"/api/workflows/{wf['id']}")).json()
    assert det["tasks"][0]["notebook_path"] == dst
    assert det["status"] != "INVALID"

    # cleanup
    await client.delete("/api/workspace/file", params={"path": d, "recursive": "true"})


async def test_delete_referenced_notebook_invalidates_workflow(client) -> None:
    d = _p("wfdel")
    path = f"{d}/job.ipynb"
    nb = {
        "nbformat": 4, "nbformat_minor": 5,
        "metadata": {"kernelspec": {"name": "python3", "display_name": "Python 3"}},
        "cells": [
            {"cell_type": "code", "metadata": {"tags": ["parameters"]}, "source": "",
             "outputs": [], "execution_count": None},
            {"cell_type": "code", "metadata": {}, "source": "x = 1\n",
             "outputs": [], "execution_count": None},
        ],
    }
    await client.put("/api/workspace/file", params={"path": path}, json={"notebook": nb})
    wf = (await client.post("/api/workflows", json={"name": _p("D")})).json()
    await client.put(
        f"/api/workflows/{wf['id']}/graph",
        json={
            "tasks": [
                {"key": "t1", "name": "j", "type": "NOTEBOOK",
                 "notebook_path": path, "ui_position": {"x": 0, "y": 0}}
            ],
            "dependencies": [],
        },
    )

    assert (
        await client.delete("/api/workspace/file", params={"path": path})
    ).status_code == 204
    assert (await client.get(f"/api/workflows/{wf['id']}")).json()["status"] == "INVALID"

    # recriar + salvar de novo → volta a DRAFT
    await client.put("/api/workspace/file", params={"path": path}, json={"notebook": nb})
    g = await client.put(
        f"/api/workflows/{wf['id']}/graph",
        json={
            "tasks": [
                {"key": "t1", "name": "j", "type": "NOTEBOOK",
                 "notebook_path": path, "ui_position": {"x": 0, "y": 0}}
            ],
            "dependencies": [],
        },
    )
    assert g.status_code == 200, g.text
    assert (await client.get(f"/api/workflows/{wf['id']}")).json()["status"] == "DRAFT"
    await client.delete("/api/workspace/file", params={"path": d, "recursive": "true"})


async def test_internal_dir_protected(client) -> None:
    assert (
        await client.put(
            "/api/workspace/file",
            params={"path": ".workspace/workspace.json"},
            json={"text": "{}"},
        )
    ).status_code == 403
    assert (
        await client.delete("/api/workspace/file", params={"path": ".workspace"})
    ).status_code == 403


async def test_generate_csv(client) -> None:
    d = _p("gen")
    r = await client.post(
        "/api/workspace/generate",
        json={"path": f"{d}/bi.csv", "rows": 20_000, "seed": 1},
    )
    assert r.status_code == 201, r.text
    prev = (
        await client.get(
            "/api/workspace/data", params={"path": f"{d}/bi.csv", "limit": 50}
        )
    ).json()
    assert prev["columns"][0] == "id" and len(prev["rows"]) == 50
    await client.delete("/api/workspace/file", params={"path": d, "recursive": "true"})
