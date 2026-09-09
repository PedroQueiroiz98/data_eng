"""Watcher de filesystem do Workspace único → eventos em tempo real.

`watchfiles.awatch` observa `settings.workspace_dir` e publica lotes de mudanças
(`fs.batch`) no canal Redis `nbp:events:workspace`, consumido pelo WebSocket
`/ws/workspace`. Cobre TODA escrita: API HTTP, células do kernel, saídas do
Papermill, git — qualquer coisa que toque o disco.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from pathlib import Path, PurePosixPath

from watchfiles import Change, awatch

from nbplatform.core.config import get_settings
from nbplatform.queue.redis_client import get_redis
from nbplatform.ws.events import publish_workspace_event

logger = logging.getLogger("nbplatform.workspace.watcher")

_OP = {
    Change.added: "created",
    Change.modified: "updated",
    Change.deleted: "deleted",
}

# Diretórios/arquivos internos que não interessam ao File Explorer.
_IGNORED_TOP = {".workspace", ".git"}
_TMP_PREFIXES = (".write-", ".gen-", ".upload-", ".~", "~")


def _rel(root: Path, abspath: str) -> str | None:
    try:
        rel = Path(abspath).resolve().relative_to(root.resolve())
    except (ValueError, OSError):
        return None
    parts = rel.parts
    if not parts:
        return None
    if parts[0] in _IGNORED_TOP:
        return None
    if any(p.startswith(_TMP_PREFIXES) for p in parts):
        return None
    return PurePosixPath(*parts).as_posix()


def map_changes(root: Path, raw: set[tuple[Change, str]]) -> list[dict[str, object]]:
    """Converte o conjunto bruto do watchfiles em eventos normalizados, deduplicados."""
    seen: dict[str, dict[str, object]] = {}
    for change, abspath in raw:
        op = _OP.get(change)
        if op is None:
            continue
        rel = _rel(root, abspath)
        if rel is None:
            continue
        is_dir = False
        if op != "deleted":
            with contextlib.suppress(OSError):
                is_dir = Path(abspath).is_dir()
        # `deleted` vence `created/updated` do mesmo path no mesmo lote.
        prev = seen.get(rel)
        if prev is not None and prev["op"] == "deleted":
            continue
        seen[rel] = {"op": op, "path": rel, "is_dir": is_dir}
    return list(seen.values())


async def run_workspace_watcher(stop: asyncio.Event) -> None:
    settings = get_settings()
    root = Path(settings.workspace_dir)
    root.mkdir(parents=True, exist_ok=True)
    redis = get_redis()
    debounce = settings.workspace_watch_debounce_ms
    logger.info("workspace watcher iniciado", extra={"root": str(root)})
    try:
        async for raw in awatch(
            str(root),
            stop_event=stop,
            debounce=debounce,
            recursive=True,
            ignore_permission_denied=True,
        ):
            changes = map_changes(root, raw)
            if not changes:
                continue
            event = {"type": "fs.batch", "changes": changes, "ts": time.time()}
            try:
                await publish_workspace_event(redis, event)
            except Exception:  # noqa: BLE001 - publicar evento nunca derruba o watcher
                logger.warning("falha ao publicar fs.batch", exc_info=True)
    except asyncio.CancelledError:
        raise
    except Exception:  # noqa: BLE001
        logger.exception("workspace watcher morreu")
    finally:
        logger.info("workspace watcher parado")
