"""Ponte entre o autocomplete (LSP) e o kernel Python interativo.

Quando existe uma sessão de kernel ociosa para o notebook aberto, pedimos ao
kernel um `complete_request` (introspecção do Jupyter — NÃO executa código) e
mesclamos o resultado com o do Jedi: o kernel ganha para atributos de objetos
vivos (`df.` depois de `df = carrega()`), o Jedi cobre stdlib e nomes ainda não
atribuídos. Qualquer falha → só Jedi.
"""

from __future__ import annotations

import json
import math
import uuid
from dataclasses import dataclass, field

from redis.asyncio import Redis

from nbplatform.core.config import get_settings
from nbplatform.services.lsp.jedi_backend import Completion
from nbplatform.services.lsp.secret_names import is_sensitive_name

# tipos "experimentais" do Jupyter → kind do nosso protocolo de completion
_JUP_KIND = {
    "function": "function",
    "class": "class",
    "instance": "instance",
    "keyword": "keyword",
    "module": "module",
    "statement": "statement",
    "param": "param",
    "magic": "keyword",
    "path": "path",
    "dict key": "property",
}


@dataclass(frozen=True)
class KernelCompletion:
    matches: list[str] = field(default_factory=list)
    cursor_start: int | None = None
    cursor_end: int | None = None
    types: dict[str, str] = field(default_factory=dict)

    def __bool__(self) -> bool:
        return bool(self.matches)


def cursor_offset(code: str, line0: int, col0: int) -> int:
    """(linha 0-based, coluna 0-based) → offset absoluto no texto da célula."""
    lines = code.split("\n")
    line0 = max(0, min(line0, len(lines) - 1))
    col0 = max(0, min(col0, len(lines[line0])))
    return sum(len(ln) + 1 for ln in lines[:line0]) + col0


async def request_completion(
    redis: Redis,
    session_id: str,
    code: str,
    cursor_pos: int,
    timeout_s: float,
) -> KernelCompletion | None:
    """Pede um `complete_request` ao kernel-worker e espera a resposta (Redis)."""
    settings = get_settings()
    request_id = uuid.uuid4().hex
    op = {
        "op": "complete",
        "session_id": session_id,
        "code": code,
        "cursor_pos": cursor_pos,
        "request_id": request_id,
    }
    rpc_key = settings.kernel_rpc_key(request_id)
    try:
        await redis.rpush(settings.redis_kernel_ops, json.dumps(op))
        raw = await redis.blpop([rpc_key], timeout=max(1, math.ceil(timeout_s)))
    except Exception:  # noqa: BLE001 - qualquer falha → só Jedi
        return None
    if not raw:
        return None
    try:
        _key, value = raw
        payload = json.loads(value)
    except (ValueError, TypeError):
        return None
    matches = [str(m) for m in payload.get("matches", [])]
    types: dict[str, str] = {}
    exp = (payload.get("metadata") or {}).get("_jupyter_types_experimental") or []
    for entry in exp:
        if isinstance(entry, dict) and entry.get("text"):
            types[str(entry["text"])] = str(entry.get("type") or "")
    return KernelCompletion(
        matches=matches,
        cursor_start=payload.get("cursor_start"),
        cursor_end=payload.get("cursor_end"),
        types=types,
    )


def _kind_for(name: str, raw_type: str) -> str:
    mapped = _JUP_KIND.get(raw_type.strip().lower()) if raw_type else None
    if mapped:
        return mapped
    return "function" if name.endswith("(") else "instance"


def merge(
    jedi_items: list[Completion], kc: KernelCompletion | None, prefix: str
) -> list[Completion]:
    """Kernel primeiro (objetos vivos), depois os itens do Jedi que faltam."""
    if not kc:
        return jedi_items
    seen: set[str] = set()
    out: list[Completion] = []
    for raw in kc.matches:
        # o kernel devolve o token completo (ex.: `df.columns`); pega só o sufixo
        label = raw.split(".")[-1] if "." in raw else raw
        label = label.rstrip("(")
        if not label or label in seen or is_sensitive_name(label):
            continue
        if prefix and not label.startswith(prefix):
            continue
        seen.add(label)
        call = raw.endswith("(") or _kind_for(raw, kc.types.get(raw, "")) in (
            "function",
            "class",
        )
        out.append(
            Completion(
                label=label,
                insert_text=label,
                kind=_kind_for(raw, kc.types.get(raw, "")),
                detail="kernel",
                documentation="",
                call=call,
            )
        )
    for it in jedi_items:
        if it.label in seen:
            continue
        seen.add(it.label)
        out.append(it)
    return out
