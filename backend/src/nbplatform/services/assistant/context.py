"""Montagem do contexto enviado para a IA — limitado e SANITIZADO (spec §8/§9/§14).

Estratégia:
1. célula atual (INLINE: dividida no cursor);
2. células anteriores relevantes (import/def/class/=), de trás pra frente;
3. imports (sempre);
4. nomes definidos (via `ast`, SEM executar nada);
5. erro da última execução (ename/evalue + fim do traceback);
6. arquivos do workspace referenciados (nomes + trecho inicial), best-effort;
7. redação de segredos em TODA string que vai no payload;
8. corte por orçamento de caracteres, na ordem de prioridade acima.
"""

from __future__ import annotations

import ast
import re
import uuid
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from nbplatform.core.config import get_settings
from nbplatform.core.masking import is_sensitive_key, mask_secrets
from nbplatform.domain.assistant import AssistantContext, AssistantTask, cursor_offset
from nbplatform.services.lsp.secret_names import is_sensitive_name
from nbplatform.services.secret_service import SecretService

_IMPORT_RE = re.compile(r"^\s*(?:import\s+\S|from\s+\S+\s+import\s+\S)")
_RELEVANT_RE = re.compile(r"^\s*(?:import\s|from\s|def\s|class\s|@)|=")
_READ_PATH_RE = re.compile(
    r"""(?:read_csv|read_parquet|read_json|read_excel|read_table|open|Path)\s*\(\s*['"]([^'"]+)['"]"""
)
_ASSIGN_LHS_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*(?::[^=]+)?=")
_SECRETY_RE = re.compile(
    r"(sk-[A-Za-z0-9_-]{12,}|Bearer\s+[A-Za-z0-9._-]{12,}|[A-Za-z0-9+/]{40,}={0,2})"
)
_SENSITIVE_INDEX_RE = re.compile(r"\[\s*['\"]([^'\"]+)['\"]\s*\]")

_MAX_TRACEBACK_LINES = 15
_MAX_WS_FILES = 3
_MAX_WS_FILE_LINES = 40
_CELL_TRIM = 4000


def _neutralize_magics(src: str) -> str:
    out: list[str] = []
    for line in src.split("\n"):
        s = line.lstrip()
        out.append(line if not (s.startswith("%") or s.startswith("!")) else "")
    return "\n".join(out)


def _redact(text: str, secret_values: list[str]) -> str:
    if not text:
        return text
    if secret_values:
        text = mask_secrets(text, secret_values)
    lines_out: list[str] = []
    for line in text.split("\n"):
        m = _ASSIGN_LHS_RE.match(line)
        if m and is_sensitive_name(m.group(1)):
            lines_out.append(f"{m.group(1)} = '***'")
            continue
        # env sensível: os.environ["DB_PASSWORD"] etc.
        if "os.environ" in line and _SENSITIVE_INDEX_RE.search(line):
            lines_out.append(_SENSITIVE_INDEX_RE.sub("[...]", line))
            continue
        lines_out.append(_SECRETY_RE.sub("«redacted»", line))
    return "\n".join(lines_out)


def _defined_names(cells: list[str]) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for src in cells:
        try:
            tree = ast.parse(_neutralize_magics(src))
        except SyntaxError:
            continue
        for node in tree.body:
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                _add(names, seen, node.name)
            elif isinstance(node, ast.Assign):
                for tgt in node.targets:
                    if isinstance(tgt, ast.Name):
                        _add(names, seen, tgt.id)
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                _add(names, seen, node.target.id)
            elif isinstance(node, ast.Import | ast.ImportFrom):
                for alias in node.names:
                    _add(names, seen, alias.asname or alias.name.split(".")[0])
    return names


def _add(names: list[str], seen: set[str], name: str) -> None:
    if name and name not in seen and not is_sensitive_name(name):
        seen.add(name)
        names.append(name)


def _imports(cells: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for src in cells:
        for line in src.split("\n"):
            if _IMPORT_RE.match(line):
                st = line.strip()
                if st not in seen:
                    seen.add(st)
                    out.append(st)
    return out


def _format_error(err: dict[str, object] | None, secret_values: list[str]) -> str | None:
    if not err:
        return None
    ename = str(err.get("ename") or "")
    evalue = str(err.get("evalue") or "")
    tb = err.get("traceback") or []
    tail = [str(x) for x in tb][-_MAX_TRACEBACK_LINES:] if isinstance(tb, list) else []
    text = f"{ename}: {evalue}".strip(": ")
    if tail:
        text += "\n" + "\n".join(tail)
    return _redact(text, secret_values)


async def _workspace_files(
    session: AsyncSession,
    user_id: uuid.UUID | None,
    current_cell: str,
    hinted: list[str] | None,
    secret_values: list[str],
) -> list[str]:
    if user_id is None:
        return []
    rel_paths: list[str] = list(hinted or [])
    for m in _READ_PATH_RE.finditer(current_cell):
        rel_paths.append(m.group(1))
    rel_paths = [p for p in dict.fromkeys(rel_paths) if not is_sensitive_key(p)][:_MAX_WS_FILES]
    if not rel_paths:
        return []
    from nbplatform.services.workspace_fs_service import WorkspaceFsService

    home = Path(get_settings().workspace_dir) / str(user_id)
    if not home.is_dir():
        return []
    fs = WorkspaceFsService(
        home,
        max_upload_bytes=get_settings().workspace_max_upload_bytes,
        max_nodes=get_settings().workspace_tree_max_nodes,
        max_depth=get_settings().workspace_tree_max_depth,
    )
    out: list[str] = []
    for rel in rel_paths:
        try:
            content = await fs.read_file(rel.lstrip("./"))
        except Exception:  # noqa: BLE001 - arquivo ausente/binário → ignora
            continue
        if not isinstance(content.content, str):
            continue
        head = "\n".join(content.content.split("\n")[:_MAX_WS_FILE_LINES])
        out.append(f"## {rel}\n{_redact(head, secret_values)}")
    return out


async def build_context(
    session: AsyncSession,
    *,
    cells: list[str],
    active_index: int,
    cursor_line: int | None,
    cursor_col: int | None,
    task: AssistantTask,
    recent_error: dict[str, object] | None = None,
    workspace_files: list[str] | None = None,
    selection: str | None = None,
    user_id: uuid.UUID | None = None,
    budget_chars: int | None = None,
    max_cells: int | None = None,
) -> AssistantContext:
    settings = get_settings()
    budget = budget_chars or settings.assistant_context_max_chars
    max_cells = max_cells or settings.assistant_context_max_cells

    try:
        secret_values = [
            v for v in (await SecretService(session).resolve_all()).values() if v and len(v) >= 4
        ]
    except Exception:  # noqa: BLE001
        secret_values = []

    active_index = max(0, min(active_index, len(cells) - 1)) if cells else 0
    current = _redact(cells[active_index] if cells else "", secret_values)[:_CELL_TRIM]

    cursor_prefix = cursor_suffix = None
    if task is AssistantTask.INLINE and cursor_line is not None and cursor_col is not None:
        raw = cells[active_index] if cells else ""
        off = cursor_offset(raw, cursor_line, cursor_col)
        cursor_prefix = _redact(raw[:off], secret_values)[-_CELL_TRIM:]
        cursor_suffix = _redact(raw[off:], secret_values)[:1000]

    preceding: list[str] = []
    used = len(current) + len(cursor_prefix or "") + len(cursor_suffix or "")
    for i in range(active_index - 1, -1, -1):
        if len(preceding) >= max_cells or used >= budget:
            break
        src = cells[i]
        if not _RELEVANT_RE.search(src):
            continue
        snippet = _redact(src, secret_values)[:_CELL_TRIM]
        preceding.insert(0, snippet)
        used += len(snippet)

    imports = [_redact(s, secret_values) for s in _imports(cells)]
    defined = _defined_names(cells)
    error_text = _format_error(recent_error, secret_values)
    ws_files = await _workspace_files(
        session, user_id, cells[active_index] if cells else "", workspace_files, secret_values
    )

    # corte final por orçamento (prioridade: atual > erro > imports > nomes > anteriores > arquivos)
    total = (
        len(current)
        + len(error_text or "")
        + sum(len(x) for x in imports)
        + sum(len(x) for x in defined)
        + sum(len(x) for x in preceding)
        + sum(len(x) for x in ws_files)
    )
    while total > budget:
        if ws_files:
            total -= len(ws_files.pop())
        elif preceding:
            total -= len(preceding.pop(0))
        elif len(defined) > 20:
            total -= len(defined.pop())
        elif imports and len(imports) > 5:
            total -= len(imports.pop())
        else:
            break

    return AssistantContext(
        language="python",
        current_cell=current,
        cursor_prefix=cursor_prefix,
        cursor_suffix=cursor_suffix,
        preceding_cells=preceding,
        imports=imports,
        defined_names=defined[:60],
        recent_error=error_text,
        workspace_files=ws_files,
        selection=_redact(selection, secret_values) if selection else None,
    )
