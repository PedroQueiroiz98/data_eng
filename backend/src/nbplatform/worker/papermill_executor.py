"""Spawn e supervisão do subprocesso Papermill (isolamento por processo; Docker vem na Fase 8)."""

from __future__ import annotations

import asyncio
import contextlib
import sys
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from nbplatform.worker.papermill_runner import EXIT_NOTEBOOK_ERROR, EXIT_OK

LineHandler = Callable[[str], Awaitable[None]]

ERROR_PREFIX = "PAPERMILL_ERROR::"


@dataclass(frozen=True)
class PapermillResult:
    exit_code: int
    timed_out: bool
    cancelled: bool
    error_summary: str | None

    @property
    def succeeded(self) -> bool:
        return self.exit_code == EXIT_OK and not self.timed_out and not self.cancelled

    @property
    def is_notebook_error(self) -> bool:
        return (
            self.exit_code == EXIT_NOTEBOOK_ERROR
            and not self.timed_out
            and not self.cancelled
        )


async def run_papermill(
    *,
    input_path: str,
    output_path: str,
    params_path: str,
    timeout_s: float,
    on_line: LineHandler,
    cancel_event: asyncio.Event | None = None,
) -> PapermillResult:
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "nbplatform.worker.papermill_runner",
        input_path,
        output_path,
        params_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )

    error_summary: str | None = None
    assert proc.stdout is not None

    async def _pump() -> None:
        nonlocal error_summary
        async for raw in proc.stdout:  # type: ignore[union-attr]
            line = raw.decode(errors="replace").rstrip("\n")
            if not line:
                continue
            if line.startswith(ERROR_PREFIX):
                error_summary = line[len(ERROR_PREFIX) :]
            await on_line(line)

    async def _watch_cancel() -> None:
        if cancel_event is None:
            await asyncio.Future()  # nunca resolve
        else:
            await cancel_event.wait()

    pump_task = asyncio.create_task(_pump())
    wait_task = asyncio.create_task(proc.wait())
    cancel_task = asyncio.create_task(_watch_cancel())

    timed_out = False
    cancelled = False
    try:
        done, _ = await asyncio.wait(
            {wait_task, cancel_task}, timeout=timeout_s, return_when=asyncio.FIRST_COMPLETED
        )
        if not done:
            timed_out = True
        elif cancel_task in done:
            cancelled = True
    finally:
        if timed_out or cancelled:
            proc.kill()
        with contextlib.suppress(ProcessLookupError):
            await proc.wait()
        cancel_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await cancel_task
        with contextlib.suppress(Exception):
            await pump_task

    if timed_out:
        await on_line(f"{ERROR_PREFIX}timeout após {timeout_s:.0f}s — processo terminado")
    elif cancelled:
        await on_line(f"{ERROR_PREFIX}cancelado — processo terminado")

    return PapermillResult(
        exit_code=proc.returncode if proc.returncode is not None else -1,
        timed_out=timed_out,
        cancelled=cancelled,
        error_summary=error_summary,
    )
