"""Sandbox Docker hardened para execução de notebook.

O container de execução:
- não é privilegiado e NÃO monta o socket do Docker;
- roda como usuário não-root (uid 1000, definido na imagem);
- filesystem read-only + tmpfs em /tmp;
- limites de CPU, memória e PIDs;
- sem rede (--network none) por padrão;
- timeout (kill do container).
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Awaitable, Callable

from nbplatform.core.config import get_settings
from nbplatform.worker.papermill_executor import ERROR_PREFIX, PapermillResult

LineHandler = Callable[[str], Awaitable[None]]

_CONTAINER_WORKDIR = "/work"


def build_docker_args(
    *,
    container_name: str,
    workdir: str,
    env: dict[str, str],
    image: str,
    cpus: str,
    memory: str,
    pids_limit: int,
) -> list[str]:
    args = [
        "docker",
        "run",
        "--rm",
        "--name",
        container_name,
        "--network",
        "none",
        "--cpus",
        cpus,
        "--memory",
        memory,
        "--memory-swap",
        memory,
        "--pids-limit",
        str(pids_limit),
        "--read-only",
        "--tmpfs",
        "/tmp:rw,size=128m",
        "--security-opt",
        "no-new-privileges",
        "--cap-drop",
        "ALL",
        "-v",
        f"{workdir}:{_CONTAINER_WORKDIR}:rw",
        "-w",
        _CONTAINER_WORKDIR,
    ]
    for key, value in env.items():
        args += ["-e", f"{key}={value}"]
    args += [
        image,
        "python",
        "-m",
        "nbplatform.worker.papermill_runner",
        f"{_CONTAINER_WORKDIR}/input.ipynb",
        f"{_CONTAINER_WORKDIR}/output.ipynb",
        f"{_CONTAINER_WORKDIR}/params.json",
    ]
    return args


async def run_in_docker(
    *,
    workdir: str,
    input_path: str,  # noqa: ARG001 - o container usa caminhos fixos em /work
    output_path: str,  # noqa: ARG001
    params_path: str,  # noqa: ARG001
    env: dict[str, str],
    timeout_s: float,
    on_line: LineHandler,
    cancel_event: asyncio.Event | None = None,
) -> PapermillResult:
    settings = get_settings()
    container_name = f"nbp-exec-{workdir.rstrip('/').rsplit('/', 1)[-1][:24]}"
    args = build_docker_args(
        container_name=container_name,
        workdir=workdir,
        env=env,
        image=settings.sandbox_image,
        cpus=settings.sandbox_cpus,
        memory=settings.sandbox_memory,
        pids_limit=settings.sandbox_pids_limit,
    )
    await on_line(f"docker run ({settings.sandbox_image}, cpus={settings.sandbox_cpus})")

    proc = await asyncio.create_subprocess_exec(
        *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
    )
    assert proc.stdout is not None
    error_summary: str | None = None

    async def _pump() -> None:
        nonlocal error_summary
        async for raw in proc.stdout:  # type: ignore[union-attr]
            line = raw.decode(errors="replace").rstrip("\n")
            if not line:
                continue
            if line.startswith(ERROR_PREFIX):
                error_summary = line[len(ERROR_PREFIX) :]
            await on_line(line)

    async def _kill_container() -> None:
        with contextlib.suppress(Exception):
            killer = await asyncio.create_subprocess_exec(
                "docker", "kill", container_name,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await killer.wait()

    async def _watch_cancel() -> None:
        if cancel_event is None:
            await asyncio.Event().wait()  # nunca resolve
        else:
            await cancel_event.wait()

    pump_task = asyncio.create_task(_pump())
    wait_task = asyncio.create_task(proc.wait())
    cancel_task: asyncio.Task[None] = asyncio.create_task(_watch_cancel())

    timed_out = cancelled = False
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
            await _kill_container()
        with contextlib.suppress(ProcessLookupError):
            await proc.wait()
        cancel_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await cancel_task
        with contextlib.suppress(Exception):
            await pump_task

    if timed_out:
        await on_line(f"{ERROR_PREFIX}timeout após {timeout_s:.0f}s — container terminado")
    elif cancelled:
        await on_line(f"{ERROR_PREFIX}cancelado — container terminado")

    return PapermillResult(
        exit_code=proc.returncode if proc.returncode is not None else -1,
        timed_out=timed_out,
        cancelled=cancelled,
        error_summary=error_summary,
    )
