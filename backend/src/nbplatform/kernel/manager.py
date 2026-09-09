"""Orquestrador do processo `kernel-worker`.

Consome `nbp:kernel:ops` (Redis list), mantém as sessões de kernel em memória e
publica eventos por sessão em `nbp:events:kernel:{id}` (+ buffer em lista para o
snapshot/resume do WebSocket).
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import time
from pathlib import Path
from typing import Any

from redis.asyncio import Redis

from nbplatform.core.config import get_settings
from nbplatform.kernel.env import resolve_workspace_env
from nbplatform.kernel.session import KernelSession
from nbplatform.ws.events import publish_kernel_event

logger = logging.getLogger(__name__)


class KernelSessionManager:
    def __init__(self, redis: Redis) -> None:
        self.redis = redis
        self.settings = get_settings()
        self.sessions: dict[str, KernelSession] = {}
        self._ensure_lock = asyncio.Lock()
        self._tasks: set[asyncio.Task[Any]] = set()

    # ── eventos ──────────────────────────────────────────────────────────────
    async def _emit(self, session_id: str, event: dict[str, Any]) -> None:
        seq = await self.redis.incr(self.settings.kernel_seq_key(session_id))
        payload = {**event, "seq": seq}
        log_key = self.settings.kernel_log_key(session_id)
        raw = json.dumps(payload, default=str)
        await self.redis.rpush(log_key, raw)
        await self.redis.ltrim(log_key, -self.settings.kernel_event_buffer, -1)
        ttl = int(self.settings.kernel_idle_timeout_s * 2)
        await self.redis.expire(log_key, ttl)
        sess_key = self.settings.kernel_sess_key(session_id)
        if event["type"] == "kernel.status":
            await self.redis.hset(sess_key, "status", event["status"])
            await self.redis.expire(sess_key, ttl)
        elif event["type"] == "cell.finished" and event.get("execution_count") is not None:
            await self.redis.hset(sess_key, "execution_count", str(event["execution_count"]))
        await publish_kernel_event(self.redis, session_id, payload)

    def _emitter(self, session_id: str):  # type: ignore[no-untyped-def]
        async def _fn(event: dict[str, Any]) -> None:
            await self._emit(session_id, event)

        return _fn

    # ── lifecycle ────────────────────────────────────────────────────────────
    async def ensure(self, session_id: str) -> KernelSession | None:
        async with self._ensure_lock:
            sess = self.sessions.get(session_id)
            if sess is not None and sess.status != "dead":
                return sess
            if sess is not None:
                self.sessions.pop(session_id, None)

            raw_meta = await self.redis.hgetall(self.settings.kernel_sess_key(session_id))
            meta = {str(k): str(v) for k, v in raw_meta.items()}
            if "workspace_id" not in meta:
                logger.warning("sessão de kernel sem metadados: %s", session_id)
                return None

            if len(self.sessions) >= self.settings.kernel_max_sessions:
                await self._evict_idle()

            # Isolamento por usuário: raiz = Home do dono da sessão
            # (`{workspace_dir}/{user_id}`). `notebook_path` é relativo à Home.
            ws_root = Path(self.settings.workspace_dir) / str(meta["user_id"])
            # cwd = pasta do notebook (convenção Jupyter/Databricks: `../data/x.csv`
            # resolve a partir de onde o notebook está). WORKSPACE_ROOT = a Home.
            nb_path = meta.get("notebook_path", "")
            cwd = ws_root
            if nb_path:
                cand = (ws_root / nb_path).parent
                if cand.is_dir():
                    cwd = cand
            env, secret_values = await resolve_workspace_env(str(ws_root))
            sess = KernelSession(
                session_id,
                cwd=str(cwd),
                env=env,
                secret_values=secret_values,
                startup_timeout=self.settings.kernel_startup_timeout_s,
                exec_timeout=self.settings.kernel_exec_timeout_s,
            )
            self.sessions[session_id] = sess
            emit = self._emitter(session_id)
            try:
                await sess.start(emit)
            except Exception:  # noqa: BLE001
                logger.exception("falha ao iniciar kernel %s", session_id)
                self.sessions.pop(session_id, None)
                return None
            sess.task = asyncio.create_task(sess.worker(emit))
            return sess

    async def execute(self, session_id: str, cell_id: str, code: str, request_id: str) -> None:
        sess = await self.ensure(session_id)
        if sess is None or sess.status == "dead":
            await self._emit(
                session_id,
                {
                    "type": "cell.error",
                    "cell_id": cell_id,
                    "request_id": request_id,
                    "output": {
                        "output_type": "error",
                        "ename": "KernelError",
                        "evalue": "kernel indisponível — reinicie o kernel",
                        "traceback": [],
                    },
                },
            )
            await self._emit(
                session_id,
                {
                    "type": "cell.finished",
                    "cell_id": cell_id,
                    "request_id": request_id,
                    "status": "error",
                    "execution_count": None,
                    "duration_ms": 0,
                    "outputs": [],
                },
            )
            return
        await sess.enqueue(
            {"op": "execute", "cell_id": cell_id, "code": code, "request_id": request_id}
        )

    async def interrupt(self, session_id: str) -> None:
        sess = self.sessions.get(session_id)
        if sess is not None:
            await sess.interrupt()

    async def restart(self, session_id: str) -> None:
        sess = await self.ensure(session_id)
        if sess is not None:
            await sess.request_restart()

    async def shutdown(self, session_id: str) -> None:
        sess = self.sessions.pop(session_id, None)
        if sess is None:
            return
        if sess.task is not None:
            with contextlib.suppress(Exception):
                await sess.stop_worker()
                await asyncio.wait_for(sess.task, timeout=5)
        await sess.shutdown()
        await self.redis.delete(
            self.settings.kernel_sess_key(session_id),
            self.settings.kernel_seq_key(session_id),
            self.settings.kernel_log_key(session_id),
        )

    async def shutdown_all(self) -> None:
        for sid in list(self.sessions):
            with contextlib.suppress(Exception):
                await self.shutdown(sid)

    async def _evict_idle(self) -> None:
        idle = sorted(
            (s.last_activity, sid) for sid, s in self.sessions.items() if s.status != "busy"
        )
        if idle:
            logger.info("limite de kernels atingido; despejando %s", idle[0][1])
            await self.shutdown(idle[0][1])

    async def reap(self) -> None:
        now = time.time()
        for sid, sess in list(self.sessions.items()):
            if sess.status == "busy":
                continue
            if now - sess.last_activity > self.settings.kernel_idle_timeout_s:
                logger.info("reaping kernel ocioso %s", sid)
                await self.shutdown(sid)

    # ── loop principal ───────────────────────────────────────────────────────
    async def run(self, stop: asyncio.Event) -> None:
        reaper = asyncio.create_task(self._reaper_loop(stop))
        logger.info("kernel-worker consumindo %s", self.settings.redis_kernel_ops)
        try:
            while not stop.is_set():
                raw = await self.redis.blpop(self.settings.redis_kernel_ops, timeout=2)
                if raw is None:
                    continue
                _, payload = raw
                try:
                    op = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                task = asyncio.create_task(self._dispatch(op))
                self._tasks.add(task)
                task.add_done_callback(self._tasks.discard)
        finally:
            reaper.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await reaper
            for t in list(self._tasks):
                t.cancel()
            await self.shutdown_all()

    async def _dispatch(self, op: dict[str, Any]) -> None:
        kind = op.get("op")
        sid = op.get("session_id")
        if not sid:
            return
        try:
            if kind == "ensure":
                await self.ensure(sid)
            elif kind == "execute":
                await self.execute(sid, op["cell_id"], op["code"], op["request_id"])
            elif kind == "interrupt":
                await self.interrupt(sid)
            elif kind == "restart":
                await self.restart(sid)
            elif kind == "shutdown":
                await self.shutdown(sid)
        except Exception:  # noqa: BLE001
            logger.exception("erro no dispatch %s (%s)", kind, sid)

    async def _reaper_loop(self, stop: asyncio.Event) -> None:
        while not stop.is_set():
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(stop.wait(), timeout=self.settings.kernel_reaper_interval_s)
            if stop.is_set():
                break
            with contextlib.suppress(Exception):
                await self.reap()
