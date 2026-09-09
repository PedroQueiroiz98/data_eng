"""Wrapper fino sobre o Jedi. Sem estado — um `Script` por chamada.

O Jedi é síncrono; o service chama estas funções via um pool de threads dedicado
com timeout. Erros do Jedi viram resultado vazio no service (degradação graciosa).

Duas estratégias de `jedi.Script`:

- **rápida** (`_script_fast`, `path=None`, sem projeto): usada por
  completion/hover/signature — operações por-tecla. Sem `path` o Jedi resolve
  símbolos só dentro do próprio buffer e NÃO varre o diretório de trabalho
  (que na Home do usuário fica cheio de CSVs/notebooks e derruba a latência).
- **com projeto** (`_script_project`): usada só por `goto`/`references`
  (F12 / Shift+F12, disparadas pelo usuário, toleram latência), para resolver
  símbolos importados de `scripts/*.py`.
"""

from __future__ import annotations

import contextlib
import functools
import os
from dataclasses import dataclass, field

import jedi

_MAX_DOC = 2000
_VIRTUAL_PATH = None
# tipos do Jedi que representam algo "chamável" (ganham `()` no autocomplete)
_CALLABLE_TYPES = frozenset({"function", "method", "class"})


@dataclass(frozen=True)
class Completion:
    label: str
    insert_text: str
    kind: str
    detail: str = ""
    documentation: str = ""
    call: bool = False


@dataclass(frozen=True)
class HoverInfo:
    name: str
    kind: str
    full_name: str
    signature: str
    documentation: str


@dataclass(frozen=True)
class SignatureInfo:
    label: str
    parameters: list[str] = field(default_factory=list)
    active_parameter: int = 0
    documentation: str = ""


@dataclass(frozen=True)
class Location:
    """Posição absoluta no módulo virtual (line 1-based) ou externa."""

    line: int
    column: int
    name: str
    module_path: str | None
    module_name: str
    external: bool
    code: str = ""


@functools.lru_cache(maxsize=8)
def _environment(env_path: str) -> jedi.api.environment.Environment | None:
    if not env_path:
        return None
    try:
        return jedi.create_environment(env_path, safe=False)
    except Exception:  # noqa: BLE001 - path inválido → ambiente padrão do Jedi
        return None


@functools.lru_cache(maxsize=16)
def _project(root: str) -> jedi.Project | None:
    try:
        return jedi.Project(
            root,
            added_sys_path=[root, os.path.join(root, "scripts")],
        )
    except Exception:  # noqa: BLE001 - root inválido → sem projeto
        return None


def _buffer_path(workspace_root: str | None) -> str | None:
    if workspace_root and os.path.isdir(workspace_root):
        return os.path.join(workspace_root, "__nbp_buffer__.py")
    return _VIRTUAL_PATH


def _script_fast(source: str, env_path: str) -> jedi.Script:
    """Script sem `path` nem projeto — rápido, resolve só o próprio buffer."""
    return jedi.Script(code=source, path=_VIRTUAL_PATH, environment=_environment(env_path))


def _script_project(source: str, env_path: str, workspace_root: str | None) -> jedi.Script:
    """Script com projeto Jedi (enxerga `scripts/*.py`). Só para goto/references."""
    if workspace_root and os.path.isdir(workspace_root):
        return jedi.Script(
            code=source,
            path=os.path.join(workspace_root, "__nbp_buffer__.py"),
            environment=_environment(env_path),
            project=_project(workspace_root),
        )
    return _script_fast(source, env_path)


@functools.lru_cache(maxsize=1)
def warmup() -> None:
    """Carrega typeshed/índices do Jedi uma vez (amortiza a 1ª chamada real).

    Aquece os DOIS caminhos: o rápido (completion) e o com projeto (goto).
    """
    with contextlib.suppress(Exception):
        _script_fast("import os\nos.path.", "").complete(2, 8)
    with contextlib.suppress(Exception):
        _script_fast("import os\nos.getcwd", "").goto(2, 8)


# libs de dados de uso mais comum em notebooks — a 1ª inferência de cada uma é
# cara (parso+typeshed dos stubs) o bastante pra estourar `lsp_completion_timeout_s`
# num `df.`/`np.` real do usuário se ainda não tiver sido tocada no processo.
_COMMON_LIBS = (
    ("import pandas as pd", "pd.DataFrame()"),
    ("import numpy as np", "np.array([])"),
)


@functools.lru_cache(maxsize=1)
def warmup_libraries() -> None:
    """Aquece libs populares fora do caminho de request (ver `warmup_libraries_background`
    em `service.py`). Best-effort: lib ausente/lenta não afeta nada — roda em
    background, sem bloquear o event loop nem o startup da API."""
    for prelude, obj_expr in _COMMON_LIBS:
        line2 = f"{obj_expr}."
        source = f"{prelude}\n{line2}"
        with contextlib.suppress(Exception):
            _script_fast(source, "").complete(2, len(line2))


def _clamp(source: str, line: int, column: int) -> tuple[int, int]:
    lines = source.split("\n")
    line = max(1, min(line, len(lines)))
    column = max(0, min(column, len(lines[line - 1])))
    return line, column


def _doc(text: str | None) -> str:
    if not text:
        return ""
    text = text.strip()
    return text[:_MAX_DOC] + ("…" if len(text) > _MAX_DOC else "")


def _signature_detail(c: jedi.api.classes.BaseName, fallback: str) -> str:
    try:
        sigs = c.get_signatures()
        if sigs:
            return sigs[0].to_string()
    except Exception:  # noqa: BLE001
        pass
    return fallback


def complete(
    source: str,
    line: int,
    column: int,
    env_path: str,
    limit: int,
    signature_scan: int = 0,
    workspace_root: str | None = None,  # noqa: ARG001 - ignorado (caminho rápido)
) -> list[Completion]:
    line, column = _clamp(source, line, column)
    out: list[Completion] = []
    comps = _script_fast(source, env_path).complete(line, column, fuzzy=False)[:limit]
    for i, c in enumerate(comps):
        try:
            insert = c.name_with_symbols if c.type == "param" else c.name
        except Exception:  # noqa: BLE001
            insert = c.name
        is_call = c.type in _CALLABLE_TYPES
        detail = c.module_name or ""
        if is_call and i < signature_scan:
            detail = _signature_detail(c, detail)
        out.append(
            Completion(
                label=c.name,
                insert_text=insert,
                kind=c.type or "text",
                detail=detail,
                documentation="",  # docstring sob demanda no /resolve; evita custo aqui
                call=is_call,
            )
        )
    return out


def resolve(
    source: str, line: int, column: int, label: str, env_path: str
) -> Completion | None:
    """Detalhe + docstring de UM item de completion (chamado sob demanda)."""
    line, column = _clamp(source, line, column)
    try:
        comps = _script_fast(source, env_path).complete(line, column, fuzzy=False)
    except Exception:  # noqa: BLE001
        return None
    for c in comps:
        if c.name != label:
            continue
        is_call = c.type in _CALLABLE_TYPES
        detail = _signature_detail(c, c.module_name or "") if is_call else (c.module_name or "")
        try:
            documentation = _doc(c.docstring(raw=False))
        except Exception:  # noqa: BLE001
            documentation = ""
        return Completion(
            label=c.name,
            insert_text=c.name,
            kind=c.type or "text",
            detail=detail,
            documentation=documentation,
            call=is_call,
        )
    return None


def hover(
    source: str,
    line: int,
    column: int,
    env_path: str,
    workspace_root: str | None = None,  # noqa: ARG001 - ignorado (caminho rápido)
) -> HoverInfo | None:
    line, column = _clamp(source, line, column)
    names = _script_fast(source, env_path).help(line, column)
    if not names:
        return None
    n = names[0]
    sig = ""
    try:
        sigs = n.get_signatures()
        if sigs:
            sig = sigs[0].to_string()
    except Exception:  # noqa: BLE001
        pass
    return HoverInfo(
        name=n.name or "",
        kind=n.type or "",
        full_name=n.full_name or "",
        signature=sig,
        documentation=_doc(n.docstring(raw=False)),
    )


def signature(
    source: str,
    line: int,
    column: int,
    env_path: str,
    workspace_root: str | None = None,  # noqa: ARG001 - ignorado (caminho rápido)
) -> SignatureInfo | None:
    line, column = _clamp(source, line, column)
    sigs = _script_fast(source, env_path).get_signatures(line, column)
    if not sigs:
        return None
    s = sigs[0]
    params = [p.to_string() for p in s.params]
    idx = s.index if s.index is not None else 0
    return SignatureInfo(
        label=s.to_string(),
        parameters=params,
        active_parameter=max(0, min(idx, max(0, len(params) - 1))),
        documentation=_doc(s.docstring(raw=False)),
    )


def goto(
    source: str, line: int, column: int, env_path: str, workspace_root: str | None = None
) -> list[Location]:
    line, column = _clamp(source, line, column)
    try:
        names = _script_project(source, env_path, workspace_root).goto(
            line, column, follow_imports=True, follow_builtin_imports=False
        )
    except Exception:  # noqa: BLE001
        return []
    buf = _buffer_path(workspace_root)
    return [_to_location(n, buf) for n in names]


def references(
    source: str, line: int, column: int, env_path: str, workspace_root: str | None = None
) -> list[Location]:
    line, column = _clamp(source, line, column)
    try:
        names = _script_project(source, env_path, workspace_root).get_references(
            line, column, include_builtins=False
        )
    except Exception:  # noqa: BLE001
        return []
    buf = _buffer_path(workspace_root)
    return [_to_location(n, buf) for n in names]


def _to_location(n: jedi.api.classes.Name, buffer_path: str | None = None) -> Location:
    path = str(n.module_path) if n.module_path else None
    # Uma definição no próprio buffer (com projeto Jedi, `module_path` aponta para
    # `<home>/__nbp_buffer__.py`) NÃO é externa — mapeia para uma célula.
    in_buffer = (
        path is not None
        and buffer_path is not None
        and os.path.abspath(path) == os.path.abspath(buffer_path)
    )
    external = path is not None and not in_buffer
    code = ""
    if not external:
        try:
            code = (n.get_line_code() or "").strip()
        except Exception:  # noqa: BLE001
            code = ""
    return Location(
        line=n.line or 1,
        column=n.column or 0,
        name=n.name or "",
        module_path=path,
        module_name=n.module_name or "",
        external=external,
        code=code,
    )


def runtime_info() -> dict[str, str]:
    import platform

    return {
        "engine": "jedi",
        "jedi_version": jedi.__version__,
        "python_version": platform.python_version(),
    }
