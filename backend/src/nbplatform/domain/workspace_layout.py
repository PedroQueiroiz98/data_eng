"""Estrutura física padrão de um Workspace.

Provisionamento cria a árvore de diretórios, o `.gitignore` e o
`.workspace/workspace.json` (metadados internos autodescritivos).
"""

from __future__ import annotations

import json
import re
import unicodedata
from typing import Any

# Modo single-workspace: a raiz `/root` começa VAZIA. Nenhuma pasta padrão é
# criada — o usuário organiza a estrutura livremente. (Antes: notebooks/, data/…)
SKELETON_DIRS: tuple[str, ...] = ()

GITIGNORE_TEXT = "\n".join(
    [
        "# Gerado automaticamente pelo nbplatform ao criar o Workspace.",
        "executions/",
        "logs/",
        ".cache/",
        "__pycache__/",
        "*.pyc",
        ".ipynb_checkpoints/",
        ".pydeps/",
        "",
    ]
)

WORKSPACE_JSON_VERSION = 1


def slugify(name: str) -> str:
    """`"Data Engineering"` → `"data-engineering"`. Fallback `"workspace"`."""
    normalized = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    normalized = normalized.lower()
    normalized = re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")
    normalized = re.sub(r"-{2,}", "-", normalized)
    return normalized or "workspace"


def build_workspace_json(
    *, workspace_id: str, name: str, slug: str, created_at: str
) -> dict[str, Any]:
    return {
        "version": WORKSPACE_JSON_VERSION,
        "id": workspace_id,
        "name": name,
        "slug": slug,
        "createdAt": created_at,
        "layout": list(SKELETON_DIRS),
    }


def dump_workspace_json(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"
