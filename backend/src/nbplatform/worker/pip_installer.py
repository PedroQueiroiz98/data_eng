"""Instalação de pacotes pip num diretório isolado por execução.

O worker instala num alvo (`--target`) dentro do workdir da execução, que depois
entra no `PYTHONPATH` do runner/kernel. Nunca escreve no site-packages do sistema
e nunca executa código do usuário — `pip` roda como subprocesso controlado.
"""

from __future__ import annotations

import asyncio
import contextlib
import sys
from collections.abc import Awaitable, Callable

LineHandler = Callable[[str], Awaitable[None]]

LOG_PREFIX = "pip: "


async def install_packages(
    *,
    target_dir: str,
    packages: list[str],
    on_line: LineHandler,
    timeout_s: float,
    index_url: str | None = None,
) -> bool:
    """Instala `packages` em `target_dir`. Retorna True se o pip sair com código 0."""
    if not packages:
        return True

    args = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--target",
        target_dir,
        "--upgrade",
        "--no-input",
        "--disable-pip-version-check",
        "--no-warn-script-location",
    ]
    if index_url:
        args += ["--index-url", index_url]
    args += list(packages)

    await on_line(f"{LOG_PREFIX}install {' '.join(packages)}")

    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
    except OSError as exc:  # pip ausente, etc.
        await on_line(f"{LOG_PREFIX}falha ao iniciar pip: {exc}")
        return False

    assert proc.stdout is not None

    async def _pump() -> None:
        async for raw in proc.stdout:  # type: ignore[union-attr]
            line = raw.decode(errors="replace").rstrip("\n")
            if line:
                await on_line(f"{LOG_PREFIX}{line}")

    pump_task = asyncio.create_task(_pump())
    try:
        await asyncio.wait_for(proc.wait(), timeout=timeout_s)
    except TimeoutError:
        proc.kill()
        with contextlib.suppress(ProcessLookupError):
            await proc.wait()
        await on_line(f"{LOG_PREFIX}timeout após {timeout_s:.0f}s — instalação abortada")
        with contextlib.suppress(Exception):
            await pump_task
        return False

    with contextlib.suppress(Exception):
        await pump_task

    ok = proc.returncode == 0
    if not ok:
        await on_line(f"{LOG_PREFIX}pip terminou com código {proc.returncode}")
    return ok
