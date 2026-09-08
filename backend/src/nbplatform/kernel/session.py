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

from nbplatform.kernel.protocol import iopub_to_output

logger = logging.getLogger(__name__)

EmitFn = Callable[[dict[str, Any]], Awaitable[None]]

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
    ) -> None:
        self.session_id = session_id
        self.cwd = cwd
        self.env = env
        self.secret_values = secret_values
        self.startup_timeout = startup_timeout
        self.exec_timeout = exec_timeout
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
            try:
                await self._run_one(
                    item["cell_id"], item["code"], item["request_id"], emit
                )
            except Exception:  # noqa: BLE001
                logger.exception(
                    "erro executando célula", extra={"session_id": self.session_id}
                )
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

    async def _run_one(
        self, cell_id: str, code: str, request_id: str, emit: EmitFn
    ) -> None:
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
                    msg = await asyncio.wait_for(
                        self.kc.get_iopub_msg(), timeout=self.exec_timeout
                    )
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
