from __future__ import annotations

from nbplatform.domain.workspace_layout import (
    SKELETON_DIRS,
    build_workspace_json,
    dump_workspace_json,
    slugify,
)


def test_slugify() -> None:
    assert slugify("Data Engineering") == "data-engineering"
    assert slugify("  Núcleo  de   Dados!! ") == "nucleo-de-dados"
    assert slugify("***") == "workspace"
    assert slugify("A/B\\C") == "a-b-c"


def test_no_skeleton_dirs() -> None:
    # Modo single-workspace: a raiz `/root` começa VAZIA (sem pastas padrão).
    assert SKELETON_DIRS == ()


def test_workspace_json_roundtrip() -> None:
    data = build_workspace_json(
        workspace_id="abc", name="Demo", slug="demo", created_at="2026-09-07T00:00:00+00:00"
    )
    assert data["id"] == "abc"
    assert data["layout"] == list(SKELETON_DIRS)
    dumped = dump_workspace_json(data)
    assert dumped.endswith("\n")
    assert '"slug": "demo"' in dumped
