"""Wrapper fino sobre o Jedi. Sem estado — um `Script` por chamada.

O Jedi é síncrono; o service chama estas funções via `asyncio.to_thread` com
timeout. Erros do Jedi viram resultado vazio no service (degradação graciosa).
"""

from __future__ import annotations

import contextlib
import functools
from dataclasses import dataclass, field

import jedi  # type: ignore[import-untyped]

_MAX_DOC = 2000
# `path=None` => buffer não-salvo: o Jedi resolve símbolos dentro do próprio
# código e não varre o diretório de trabalho procurando referências (lento).
_VIRTUAL_PATH = None


@dataclass(frozen=True)
class Completion:
    label: str
    insert_text: str
    kind: str
    detail: str = ""
    documentation: str = ""


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


def _script(source: str, env_path: str) -> jedi.Script:
    return jedi.Script(code=source, path=_VIRTUAL_PATH, environment=_environment(env_path))


@functools.lru_cache(maxsize=1)
def warmup() -> None:
    """Carrega typeshed/índices do Jedi uma vez (amortiza a 1ª chamada real)."""
    with contextlib.suppress(Exception):
        _script("import os\nos.path.", "").complete(2, 8)


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


def complete(source: str, line: int, column: int, env_path: str, limit: int) -> list[Completion]:
    line, column = _clamp(source, line, column)
    out: list[Completion] = []
    for c in _script(source, env_path).complete(line, column, fuzzy=False)[:limit]:
        try:
            insert = c.name_with_symbols if c.type == "param" else c.name
        except Exception:  # noqa: BLE001
            insert = c.name
        out.append(
            Completion(
                label=c.name,
                insert_text=insert,
                kind=c.type or "text",
                detail=(c.module_name or ""),
                documentation="",  # docstring sob demanda no /resolve; evita custo aqui
            )
        )
    return out


def hover(source: str, line: int, column: int, env_path: str) -> HoverInfo | None:
    line, column = _clamp(source, line, column)
    names = _script(source, env_path).help(line, column)
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


def signature(source: str, line: int, column: int, env_path: str) -> SignatureInfo | None:
    line, column = _clamp(source, line, column)
    sigs = _script(source, env_path).get_signatures(line, column)
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


def goto(source: str, line: int, column: int, env_path: str) -> list[Location]:
    line, column = _clamp(source, line, column)
    try:
        names = _script(source, env_path).goto(
            line, column, follow_imports=True, follow_builtin_imports=False
        )
    except Exception:  # noqa: BLE001
        return []
    return [_to_location(n) for n in names]


def references(source: str, line: int, column: int, env_path: str) -> list[Location]:
    line, column = _clamp(source, line, column)
    try:
        names = _script(source, env_path).get_references(line, column, include_builtins=False)
    except Exception:  # noqa: BLE001
        return []
    return [_to_location(n) for n in names]


def _to_location(n: jedi.api.classes.Name) -> Location:
    path = str(n.module_path) if n.module_path else None
    external = path is not None
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
