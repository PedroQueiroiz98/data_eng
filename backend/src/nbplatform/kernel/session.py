"""Uma sessão de kernel = um processo de kernel + fila serial de células.

Todo acesso ao `KernelClient`/canais ZMQ acontece na MESMA task (`worker`), o que
evita o `AssertionError: self.socket is not None` de sockets zmq.asyncio criados
numa task e consumidos noutra.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import time
from collections.abc import Awaitable, Callable
from typing import Any

from jupyter_client.manager import AsyncKernelManager

from nbplatform.core.masking import mask_secrets
from nbplatform.kernel.protocol import iopub_to_output

logger = logging.getLogger(__name__)

EmitFn = Callable[[dict[str, Any]], Awaitable[None]]
RpcFn = Callable[[str, dict[str, Any]], Awaitable[None]]

_STOP = {"op": "__stop__"}
_RESTART = {"op": "__restart__"}


class KernelSession:
    def __init__(
        self,
        session_id: str,
        *,
        cwd: str,
        env: dict[str, str],
        secret_values: list[str],
        startup_timeout: float,
        exec_timeout: float,
        reply: RpcFn | None = None,
    ) -> None:
        self.session_id = session_id
        self.cwd = cwd
        self.env = env
        self.secret_values = secret_values
        self.startup_timeout = startup_timeout
        self.exec_timeout = exec_timeout
        # entrega da resposta de complete/inspect (request/reply via Redis)
        self.reply: RpcFn | None = reply
        self.km: AsyncKernelManager | None = None
        self.kc: Any = None
        self.execution_count = 0
        self.last_activity = time.time()
        self.status = "starting"
        self.queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self.task: asyncio.Task[None] | None = None

    # ── lifecycle (chamado pelo manager) ────────────────────────────────────
    async def start(self, emit: EmitFn) -> None:
        """Sobe o processo do kernel. Os canais são conectados na task `worker`."""
        self.km = AsyncKernelManager(kernel_name="python3")
        full_env = {**os.environ, **self.env}
        await self.km.start_kernel(cwd=self.cwd, env=full_env)
        await emit({"type": "kernel.status", "status": "starting"})

    async def enqueue(self, item: dict[str, Any]) -> None:
        await self.queue.put(item)

    async def request_restart(self) -> None:
        await self.queue.put(dict(_RESTART))

    async def stop_worker(self) -> None:
        await self.queue.put(dict(_STOP))

    async def interrupt(self) -> None:
        if self.km:
            with contextlib.suppress(Exception):
                await self.km.interrupt_kernel()

    async def shutdown(self) -> None:
        if self.kc:
            with contextlib.suppress(Exception):
                self.kc.stop_channels()
        if self.km:
            with contextlib.suppress(Exception):
                await self.km.shutdown_kernel(now=True)
        self.status = "dead"

    # ── loop da sessão (task dedicada) ─────────────────────────────────────
    async def worker(self, emit: EmitFn) -> None:
        try:
            await self._connect(emit)
        except Exception:  # noqa: BLE001
            logger.exception("falha ao conectar canais do kernel %s", self.session_id)
            self.status = "dead"
            await emit({"type": "kernel.status", "status": "dead", "reason": "connect failed"})
            return

        while True:
            item = await self.queue.get()
            op = item.get("op")
            if op == "__stop__":
                return
            if op == "__restart__":
                await self._do_restart(emit)
                continue
            if op in ("__complete__", "__inspect__"):
                # introspecção (não executa código); nunca derruba a sessão
                try:
                    await self._do_introspect(op, item)
                except Exception:  # noqa: BLE001
                    logger.warning(
                        "introspecção do kernel falhou",
                        extra={"session_id": self.session_id},
                    )
                continue
            try:
                await self._run_one(item["cell_id"], item["code"], item["request_id"], emit)
            except Exception:  # noqa: BLE001
                logger.exception("erro executando célula", extra={"session_id": self.session_id})
                self.status = "dead"
                await emit({"type": "kernel.status", "status": "dead", "reason": "kernel error"})
                return

    async def _connect(self, emit: EmitFn) -> None:
        assert self.km is not None
        self.kc = self.km.client()
        self.kc.start_channels()
        await self.kc.wait_for_ready(timeout=self.startup_timeout)
        self.status = "idle"
        self.last_activity = time.time()
        await emit({"type": "kernel.status", "status": "idle"})

    async def _do_restart(self, emit: EmitFn) -> None:
        assert self.km is not None
        await emit({"type": "kernel.status", "status": "restarting"})
        with contextlib.suppress(Exception):
            if self.kc:
                self.kc.stop_channels()
        await self.km.restart_kernel(now=False)
        self.kc = self.km.client()
        self.kc.start_channels()
        try:
            await self.kc.wait_for_ready(timeout=self.startup_timeout)
        except Exception as exc:  # noqa: BLE001
            self.status = "dead"
            await emit({"type": "kernel.status", "status": "dead", "reason": str(exc)})
            return
        self.execution_count = 0
        self.status = "idle"
        self.last_activity = time.time()
        await emit({"type": "kernel.status", "status": "idle", "restarted": True})

    async def _run_one(self, cell_id: str, code: str, request_id: str, emit: EmitFn) -> None:
        assert self.kc is not None
        self.status = "busy"
        self.last_activity = time.time()
        await emit({"type": "cell.started", "cell_id": cell_id, "request_id": request_id})
        started = time.perf_counter()
        outputs: list[dict[str, Any]] = []
        exec_count: int | None = None
        errored = False

        msg_id = self.kc.execute(code, allow_stdin=False, store_history=True)
        try:
            while True:
                try:
                    msg = await asyncio.wait_for(self.kc.get_iopub_msg(), timeout=self.exec_timeout)
                except TimeoutError:
                    with contextlib.suppress(Exception):
                        await self.km.interrupt_kernel()  # type: ignore[union-attr]
                    errored = True
                    outputs.append(
                        {
                            "output_type": "error",
                            "ename": "TimeoutError",
                            "evalue": f"execução excedeu {self.exec_timeout:.0f}s",
                            "traceback": [],
                        }
                    )
                    break
                if msg.get("parent_header", {}).get("msg_id") != msg_id:
                    continue
                mtype = msg["msg_type"]
                content = msg["content"]
                if mtype == "status":
                    if content.get("execution_state") == "idle":
                        break
                    continue
                if mtype == "execute_input":
                    exec_count = content.get("execution_count")
                    continue
                out = iopub_to_output(mtype, content, self.secret_values)
                if out is None:
                    continue
                outputs.append(out)
                await emit(
                    {
                        "type": "cell.error" if mtype == "error" else "cell.output",
                        "cell_id": cell_id,
                        "output": out,
                    }
                )
                if mtype == "error":
                    errored = True
        finally:
            with contextlib.suppress(Exception):
                await asyncio.wait_for(self.kc.get_shell_msg(), timeout=5)

        if exec_count is not None:
            self.execution_count = exec_count
        self.status = "idle"
        self.last_activity = time.time()
        await emit(
            {
                "type": "cell.finished",
                "cell_id": cell_id,
                "request_id": request_id,
                "status": "error" if errored else "ok",
                "execution_count": exec_count,
                "duration_ms": int((time.perf_counter() - started) * 1000),
                "outputs": outputs,
            }
        )

    # ── introspecção (complete_request / inspect_request) ──────────────────
    async def _do_introspect(self, op: str, item: dict[str, Any]) -> None:
        """Responde um `__complete__`/`__inspect__` via `self.reply` (nunca lança)."""
        request_id = str(item.get("request_id", ""))
        if self.reply is None or self.kc is None:
            if self.reply is not None:
                await self.reply(request_id, {"matches": []})
            return
        code = str(item.get("code", ""))
        cursor_pos = int(item.get("cursor_pos", len(code)))
        self.last_activity = time.time()
        try:
            if op == "__complete__":
                payload = await self._complete_reply(code, cursor_pos)
            else:
                payload = await self._inspect_reply(code, cursor_pos)
        except Exception:  # noqa: BLE001
            payload = {"matches": []} if op == "__complete__" else {"text": ""}
        await self.reply(request_id, payload)

    async def _complete_reply(self, code: str, cursor_pos: int) -> dict[str, Any]:
        assert self.kc is not None
        msg_id = self.kc.complete(code, cursor_pos)
        for _ in range(20):
            msg = await asyncio.wait_for(self.kc.get_shell_msg(), timeout=1.0)
            if msg.get("parent_header", {}).get("msg_id") != msg_id:
                continue
            if msg.get("msg_type") != "complete_reply":
                continue
            content = msg["content"]
            secrets = self.secret_values
            matches = [
                mask_secrets(str(m), secrets) if secrets else str(m)
                for m in content.get("matches", [])
            ]
            meta = content.get("metadata", {}) or {}
            return {
                "matches": matches,
                "cursor_start": content.get("cursor_start"),
                "cursor_end": content.get("cursor_end"),
                "metadata": {
                    "_jupyter_types_experimental": meta.get(
                        "_jupyter_types_experimental", []
                    ),
                },
            }
        return {"matches": []}

    async def _inspect_reply(self, code: str, cursor_pos: int) -> dict[str, Any]:
        assert self.kc is not None
        msg_id = self.kc.inspect(code, cursor_pos, detail_level=0)
        for _ in range(20):
            msg = await asyncio.wait_for(self.kc.get_shell_msg(), timeout=1.0)
            if msg.get("parent_header", {}).get("msg_id") != msg_id:
                continue
            if msg.get("msg_type") != "inspect_reply":
                continue
            content = msg["content"]
            text = str(content.get("data", {}).get("text/plain", ""))
            if self.secret_values:
                text = mask_secrets(text, self.secret_values)
            return {"found": bool(content.get("found")), "text": text}
        return {"found": False, "text": ""}
