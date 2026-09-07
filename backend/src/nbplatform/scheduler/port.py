"""Porta do scheduler.

O domínio depende só desta interface; hoje o adapter é APScheduler, amanhã pode
ser Prefect sem tocar em serviços/rotas. O scheduler **apenas cria Jobs** — nunca
executa Papermill.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID


class SchedulerPort(Protocol):
    async def start(self) -> None: ...

    async def shutdown(self) -> None: ...

    async def add_schedule(
        self, schedule_id: UUID, *, cron: str, timezone: str
    ) -> None: ...

    async def remove_schedule(self, schedule_id: UUID) -> None: ...
