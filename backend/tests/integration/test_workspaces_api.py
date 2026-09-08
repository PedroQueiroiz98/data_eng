from __future__ import annotations

import uuid

import pytest

from tests.conftest import requires_services

pytestmark = [pytest.mark.asyncio, requires_services]


def _uniq(prefix: str) -> str:
    return f"{prefix} {uuid.uuid4().hex[:8]}"


async def _make_ws(client, name: str | None = None) -> dict:
    resp = await client.post(
        "/api/workspaces", json={"name": name or _uniq("Workspace")}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_create_provisions_skeleton_and_slug(client) -> None:
    ws = await _make_ws(client, _uniq("Data Engineering"))
    assert ws["slug"].startswith("data-engineering-")
    assert ws["is_active"] is True

    tree = (await client.get(f"/api/workspaces/{ws['id']}/tree")).json()
    top = {c["name"] for c in tree["children"]}
    assert {"notebooks", "scripts", "input", "output", "configs"} <= top
    assert ".workspace" not in top  # diretório interno é ocultado


async def test_slug_collision_gets_suffix(client) -> None:
    name = _uniq("Repetido")
    a = await _make_ws(client, name)
    b = await _make_ws(client, name)
    assert b["slug"] == f"{a['slug']}-2"


async def test_file_write_read_rename_delete(client) -> None:
    ws = await _make_ws(client, "FS Ops")
    wid = ws["id"]

    r = await client.put(
        f"/api/workspaces/{wid}/file",
        params={"path": "scripts/util.py"},
        json={"text": "def f():\n    return 1\n"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["kind"] == "text"

    got = await client.get(f"/api/workspaces/{wid}/file", params={"path": "scripts/util.py"})
    assert got.json()["content"].startswith("def f()")

    mv = await client.post(
        f"/api/workspaces/{wid}/rename",
        json={"from": "scripts/util.py", "to": "scripts/helpers.py"},
    )
    assert mv.status_code == 200

    missing = await client.get(
        f"/api/workspaces/{wid}/file", params={"path": "scripts/util.py"}
    )
    assert missing.status_code == 404

    d = await client.delete(
        f"/api/workspaces/{wid}/file", params={"path": "scripts/helpers.py"}
    )
    assert d.status_code == 204


async def test_notebook_file_is_validated(client) -> None:
    ws = await _make_ws(client, "NB Val")
    wid = ws["id"]
    bad = await client.put(
        f"/api/workspaces/{wid}/file",
        params={"path": "notebooks/x.ipynb"},
        json={"notebook": {"cells": [{"nope": 1}]}},
    )
    assert bad.status_code == 422
    assert bad.json()["error"]["code"] == "validation_error"


async def test_path_traversal_blocked(client) -> None:
    ws = await _make_ws(client, "Sec")
    r = await client.get(
        f"/api/workspaces/{ws['id']}/file", params={"path": "../../../etc/passwd"}
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "forbidden"


async def test_soft_delete_hides_and_blocks_writes(client) -> None:
    ws = await _make_ws(client, "Soft Del")
    wid = ws["id"]
    assert (await client.delete(f"/api/workspaces/{wid}")).status_code == 204

    listed = (await client.get("/api/workspaces")).json()
    assert wid not in {w["id"] for w in listed}

    blocked = await client.put(
        f"/api/workspaces/{wid}/file",
        params={"path": "input/a.txt"},
        json={"text": "x"},
    )
    assert blocked.status_code == 409


async def test_generate_csv_endpoint(client) -> None:
    ws = await _make_ws(client, "Gen")
    wid = ws["id"]

    r = await client.post(
        f"/api/workspaces/{wid}/generate",
        json={"path": "data/bi_data.csv", "rows": 25_000, "seed": 1},
    )
    assert r.status_code == 201, r.text
    assert r.json()["path"] == "data/bi_data.csv"
    assert r.json()["size"] > 25_000

    # preview limitado — nunca devolve as 25k linhas
    prev = await client.get(
        f"/api/workspaces/{wid}/data",
        params={"path": "data/bi_data.csv", "limit": 100},
    )
    assert prev.status_code == 200
    body = prev.json()
    assert body["columns"] == [
        "id", "customer_id", "product_id", "date",
        "quantity", "price", "total", "region",
    ]
    assert len(body["rows"]) == 100

    # não sobrescreve
    again = await client.post(
        f"/api/workspaces/{wid}/generate",
        json={"path": "data/bi_data.csv", "rows": 10},
    )
    assert again.status_code == 409

    # limite de linhas do schema
    too_many = await client.post(
        f"/api/workspaces/{wid}/generate",
        json={"path": "data/huge.csv", "rows": 9_000_000},
    )
    assert too_many.status_code == 422


async def test_purge_blocked_when_execution_history(client) -> None:
    ws = await _make_ws(client, "Purge Hist")
    wid = ws["id"]
    nb = {
        "nbformat": 4, "nbformat_minor": 5,
        "metadata": {"kernelspec": {"name": "python3", "display_name": "Python 3"}},
        "cells": [
            {"cell_type": "code", "metadata": {"tags": ["parameters"]},
             "source": "", "outputs": [], "execution_count": None},
            {"cell_type": "code", "metadata": {}, "source": "x = 1\n",
             "outputs": [], "execution_count": None},
        ],
    }
    await client.put(
        f"/api/workspaces/{wid}/file",
        params={"path": "notebooks/n.ipynb"},
        json={"notebook": nb},
    )
    ex = await client.post(
        f"/api/workspaces/{wid}/execute",
        json={"notebook_path": "notebooks/n.ipynb", "parameters": {}},
    )
    assert ex.status_code == 202, ex.text

    # purge deve recusar com 409 (não 500) por causa da FK RESTRICT de executions
    r = await client.delete(f"/api/workspaces/{wid}", params={"purge": "true"})
    assert r.status_code == 409, r.text
    assert r.json()["error"]["code"] == "conflict"

    # soft-delete continua funcionando
    assert (await client.delete(f"/api/workspaces/{wid}")).status_code == 204


async def test_internal_dir_protected_via_api(client) -> None:
    ws = await _make_ws(client, "Protected")
    wid = ws["id"]
    w = await client.put(
        f"/api/workspaces/{wid}/file",
        params={"path": ".workspace/workspace.json"},
        json={"text": "{}"},
    )
    assert w.status_code == 403
    d = await client.delete(
        f"/api/workspaces/{wid}/file", params={"path": ".workspace"}
    )
    assert d.status_code == 403


async def test_upload_and_download(client) -> None:
    ws = await _make_ws(client, "Upload")
    wid = ws["id"]
    up = await client.post(
        f"/api/workspaces/{wid}/upload",
        params={"path": "input"},
        files={"file": ("clientes.csv", b"a,b\n1,2\n", "text/csv")},
    )
    assert up.status_code == 201, up.text
    assert up.json()["path"] == "input/clientes.csv"

    dl = await client.get(
        f"/api/workspaces/{wid}/download", params={"path": "input/clientes.csv"}
    )
    assert dl.status_code == 200
    assert dl.content == b"a,b\n1,2\n"
