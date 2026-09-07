"""Segurança de caminhos do Workspace.

Um Workspace tem uma raiz física (`/data/workspaces/<uuid>/`). Todo acesso a
arquivo passa por `resolve_within()`, que normaliza o caminho relativo pedido
pelo cliente e garante que o resultado fica **dentro** da raiz — bloqueando
path traversal (`../`), caminhos absolutos e symlinks que escapam da raiz.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from nbplatform.core.errors import DomainValidationError, ForbiddenError

# Diretórios de topo criados no provisionamento (ver domain/workspace_layout.py).
RESERVED_TOP_DIRS: frozenset[str] = frozenset(
    {
        "notebooks",
        "scripts",
        "data",
        "input",
        "output",
        "configs",
        "artifacts",
        "executions",
        ".workspace",
    }
)

# Prefixo reservado a metadados internos — nunca exposto pelo File Explorer nem
# gravável pela API de arquivos.
INTERNAL_DIR = ".workspace"

_FORBIDDEN_CHARS = ("\x00", "\\")
_MAX_REL_LEN = 1024


def normalize_rel(rel: str) -> PurePosixPath:
    """Valida e normaliza um caminho relativo vindo do cliente.

    Aceita apenas POSIX (`a/b/c.ipynb`). Rejeita: vazio, absoluto, `..`,
    NUL, barra invertida, `.` como componente, letra de drive (`C:`),
    tamanho excessivo. Retorna um `PurePosixPath` sem `.`/`..`.
    """
    if not isinstance(rel, str) or not rel.strip():
        raise DomainValidationError("Caminho vazio.")
    if len(rel) > _MAX_REL_LEN:
        raise DomainValidationError("Caminho muito longo.")
    if any(ch in rel for ch in _FORBIDDEN_CHARS):
        raise DomainValidationError("Caminho contém caracteres inválidos.")

    stripped = rel.strip()
    if stripped.startswith("/"):
        raise ForbiddenError("Caminho absoluto não permitido.")

    pure = PurePosixPath(stripped)
    if pure.is_absolute():
        raise ForbiddenError("Caminho absoluto não permitido.")
    if pure.drive or (pure.parts and ":" in pure.parts[0]):
        raise ForbiddenError("Caminho com drive não permitido.")

    parts: list[str] = []
    for part in pure.parts:
        if part in ("", "."):
            continue
        if part == "..":
            raise ForbiddenError("Path traversal não permitido.")
        parts.append(part)

    if not parts:
        raise DomainValidationError("Caminho vazio após normalização.")
    return PurePosixPath(*parts)


def resolve_within(root: Path, rel: str) -> Path:
    """Resolve `rel` dentro de `root`. Levanta `ForbiddenError` se escapar.

    `Path.resolve()` segue symlinks, então um link que aponte para fora da raiz
    faz o caminho resolvido cair fora de `root` — a checagem `is_relative_to`
    cobre esse caso mesmo para arquivos que ainda não existem.
    """
    normalized = normalize_rel(rel)
    root_resolved = root.resolve()
    candidate = (root_resolved / Path(*normalized.parts)).resolve()
    if candidate != root_resolved and not candidate.is_relative_to(root_resolved):
        raise ForbiddenError("Caminho fora do Workspace.")
    return candidate


def rel_from_root(root: Path, absolute: Path) -> str:
    """Caminho POSIX relativo à raiz (para respostas da API)."""
    return absolute.resolve().relative_to(root.resolve()).as_posix()


def is_internal(rel: str) -> bool:
    """True se o caminho toca o diretório reservado `.workspace/`."""
    try:
        first = normalize_rel(rel).parts[0]
    except (DomainValidationError, ForbiddenError):
        return False
    return first == INTERNAL_DIR


def is_ipynb(rel: str) -> bool:
    return rel.lower().endswith(".ipynb")
