"""Watcher de filesystem das Homes de usuário → eventos em tempo real.

`watchfiles.awatch` observa `settings.workspace_dir` recursivamente. Cada Home é
`{workspace_dir}/{userId}/…`. O watcher separa cada mudança pelo `userId` (1º
segmento), tira esse prefixo e publica um `fs.batch` **por usuário** no canal
`nbp:events:workspace:{userId}`, consumido pelo WebSocket `/ws/workspace`.
Cobre TODA escrita: API HTTP, células do kernel, saídas do Papermill, git.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections import defaultdict
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


def _split(root: Path, abspath: str) -> tuple[str, str] | None:
    """→ (userId, home-relative posix path) ou None se fora de uma Home / interno."""
    try:
        rel = Path(abspath).resolve().relative_to(root.resolve())
    except (ValueError, OSError):
        return None
    parts = rel.parts
    if len(parts) < 2:  # precisa de {userId}/algo
        return None
    user_id, rest = parts[0], parts[1:]
    if rest[0] in _IGNORED_TOP:
        return None
    if any(p.startswith(_TMP_PREFIXES) for p in rest):
        return None
    return user_id, PurePosixPath(*rest).as_posix()


def map_changes(root: Path, raw: set[tuple[Change, str]]) -> dict[str, list[dict[str, object]]]:
    """Converte o conjunto bruto do watchfiles em eventos normalizados por usuário."""
    by_user: dict[str, dict[str, dict[str, object]]] = defaultdict(dict)
    for change, abspath in raw:
        op = _OP.get(change)
        if op is None:
            continue
        split = _split(root, abspath)
        if split is None:
            continue
        user_id, rel = split
        is_dir = False
        if op != "deleted":
            with contextlib.suppress(OSError):
                is_dir = Path(abspath).is_dir()
        seen = by_user[user_id]
        prev = seen.get(rel)
        if prev is not None and prev["op"] == "deleted":
            continue  # `deleted` vence `created/updated` do mesmo path no lote
        seen[rel] = {"op": op, "path": rel, "is_dir": is_dir}
    return {uid: list(changes.values()) for uid, changes in by_user.items() if changes}


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
            for user_id, changes in map_changes(root, raw).items():
                event = {"type": "fs.batch", "changes": changes, "ts": time.time()}
                try:
                    await publish_workspace_event(redis, event, user_id=user_id)
                except Exception:  # noqa: BLE001 - publicar evento nunca derruba o watcher
                    logger.warning("falha ao publicar fs.batch", exc_info=True)
    except asyncio.CancelledError:
        raise
    except Exception:  # noqa: BLE001
        logger.exception("workspace watcher morreu")
    finally:
        logger.info("workspace watcher parado")
