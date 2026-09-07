"""workspace_sdk — API de arquivos do Workspace para uso dentro de notebooks.

Uso típico::

    from workspace_sdk import workspace

    df_rows = workspace.read_csv("input/clientes.csv")
    workspace.write_json({"ok": True}, "output/status.json")

Resolve tudo contra ``$WORKSPACE_ROOT`` (injetado pelo executor) e bloqueia
path traversal. Sem dependências além da stdlib — ``read_csv`` devolve
``list[dict]``; se ``pandas`` estiver instalado no notebook (via ``%pip
install pandas``), devolve um ``DataFrame``.
"""

from __future__ import annotations

from pathlib import Path

from workspace_sdk._fs import Workspace

workspace = Workspace()

# Fachada de módulo — permite `from workspace_sdk import read_csv`.
path = workspace.path
exists = workspace.exists
list = workspace.list  # noqa: A001 - API deliberada
read_text = workspace.read_text
write_text = workspace.write_text
read_json = workspace.read_json
write_json = workspace.write_json
read_csv = workspace.read_csv
write_csv = workspace.write_csv
open = workspace.open  # noqa: A001 - API deliberada


def root() -> Path:
    """Raiz do Workspace atual (``$WORKSPACE_ROOT``)."""
    return workspace.root


__all__ = [
    "Workspace",
    "workspace",
    "path",
    "exists",
    "list",
    "read_text",
    "write_text",
    "read_json",
    "write_json",
    "read_csv",
    "write_csv",
    "open",
    "root",
]
