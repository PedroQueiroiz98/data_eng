from __future__ import annotations

import pytest

from nbplatform.worker.pip_installer import install_packages


@pytest.mark.asyncio
async def test_install_packages_noop_on_empty_list() -> None:
    lines: list[str] = []

    async def sink(line: str) -> None:
        lines.append(line)

    ok = await install_packages(
        target_dir="/tmp/nonexistent", packages=[], on_line=sink, timeout_s=1.0
    )
    assert ok is True
    assert lines == []


@pytest.mark.asyncio
async def test_install_packages_times_out_and_returns_false() -> None:
    lines: list[str] = []

    async def sink(line: str) -> None:
        lines.append(line)

    # Pacote inexistente + timeout curtíssimo: nunca conclui a tempo → False.
    ok = await install_packages(
        target_dir="/tmp/nbp-test-deps",
        packages=["nbplatform-definitely-not-a-real-package-zzz"],
        on_line=sink,
        timeout_s=0.05,
    )
    assert ok is False
