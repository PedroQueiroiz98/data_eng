"""Porta do scheduler.

O domínio depende só desta interface; hoje o adapter é APScheduler, amanhã pode
ser Prefect sem tocar em serviços/rotas. O scheduler **apenas cria Jobs** — nunca
executa Papermill.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Protocol

from nbplatform.domain.schedule_spec import ScheduleSpec

OnFire = Callable[[str], Awaitable[None]]


class SchedulerPort(Protocol):
    async def start(self, *, on_fire: OnFire) -> None:
        """Sobe o scheduler. `on_fire(schedule_id)` é chamado quando um cron dispara."""
        ...

    async def sync(self, specs: list[ScheduleSpec]) -> None:
        """Reconcilia os cron jobs ativos com a lista desejada (add/remove/reschedule)."""
        ...

    async def shutdown(self) -> None: ...
