"""Validação de cron e cálculo do próximo disparo.

Isolado aqui para que o resto do código não dependa da lib de cron/scheduler.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from apscheduler.triggers.cron import CronTrigger

from nbplatform.core.errors import DomainValidationError


@dataclass(frozen=True)
class ScheduleSpec:
    id: str
    cron: str
    timezone: str


def _trigger(cron: str, timezone: str) -> CronTrigger:
    try:
        ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise DomainValidationError(f"Timezone inválido: {timezone!r}.") from exc
    try:
        return CronTrigger.from_crontab(cron, timezone=timezone)
    except ValueError as exc:
        raise DomainValidationError(f"Expressão cron inválida: {cron!r} ({exc}).") from exc


def validate_cron(cron: str, timezone: str = "UTC") -> None:
    _trigger(cron, timezone)


def next_run_after(cron: str, timezone: str, *, after: datetime) -> datetime | None:
    trigger = _trigger(cron, timezone)
    result = trigger.get_next_fire_time(None, after)
    return result
