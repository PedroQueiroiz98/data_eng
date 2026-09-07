"""Spawn e supervisão do subprocesso Papermill (isolamento por processo; Docker vem na Fase 8)."""

from __future__ import annotations

import asyncio
import contextlib
import sys
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from nbplatform.worker.papermill_runner import (
    EXIT_NOTEBOOK_ERROR,
    EXIT_OK,
)

LineHandler = Callable[[str], Awaitable[None]]

ERROR_PREFIX = "PAPERMILL_ERROR::"


@dataclass(frozen=True)
class PapermillResult:
    exit_code: int
    timed_out: bool
    error_summary: str | None

    @property
    def succeeded(self) -> bool:
        return self.exit_code == EXIT_OK and not self.timed_out

    @property
    def is_notebook_error(self) -> bool:
        return self.exit_code == EXIT_NOTEBOOK_ERROR and not self.timed_out


async def run_papermill(
    *,
    input_path: str,
    output_path: str,
    params_path: str,
    timeout_s: float,
    on_line: LineHandler,
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

    timed_out = False
    try:
        await asyncio.wait_for(asyncio.gather(_pump(), proc.wait()), timeout=timeout_s)
    except TimeoutError:
        timed_out = True
        proc.kill()
        with contextlib.suppress(ProcessLookupError):
            await proc.wait()
        await on_line(f"{ERROR_PREFIX}timeout após {timeout_s:.0f}s — processo terminado")

    return PapermillResult(
        exit_code=proc.returncode if proc.returncode is not None else -1,
        timed_out=timed_out,
        error_summary=error_summary,
    )
