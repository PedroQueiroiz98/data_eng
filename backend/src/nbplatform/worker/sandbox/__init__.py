"""Sandbox de execução: subprocesso (dev) ou container Docker hardened (Fase 8)."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from nbplatform.core.config import get_settings
from nbplatform.worker.papermill_executor import PapermillResult, run_papermill
from nbplatform.worker.sandbox.docker_sandbox import run_in_docker

logger = logging.getLogger(__name__)

LineHandler = Callable[[str], Awaitable[None]]


async def run_sandboxed(
    *,
    workdir: str,
    input_path: str,
    output_path: str,
    params_path: str,
    env: dict[str, str],
    timeout_s: float,
    on_line: LineHandler,
    cancel_event: asyncio.Event | None = None,
) -> PapermillResult:
    mode = get_settings().execution_sandbox
    if mode == "docker":
        return await run_in_docker(
            workdir=workdir,
            input_path=input_path,
            output_path=output_path,
            params_path=params_path,
            env=env,
            timeout_s=timeout_s,
            on_line=on_line,
            cancel_event=cancel_event,
        )
    return await run_papermill(
        input_path=input_path,
        output_path=output_path,
        params_path=params_path,
        env=env,
        timeout_s=timeout_s,
        on_line=on_line,
        cancel_event=cancel_event,
    )
