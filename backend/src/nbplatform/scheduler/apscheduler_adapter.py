"""Adapter APScheduler para a SchedulerPort."""

from __future__ import annotations

import contextlib
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from nbplatform.domain.schedule_spec import ScheduleSpec
from nbplatform.scheduler.port import OnFire

logger = logging.getLogger(__name__)

_JOB_PREFIX = "sched:"


class APSchedulerAdapter:
    def __init__(self) -> None:
        self._scheduler = AsyncIOScheduler(timezone="UTC")
        self._on_fire: OnFire | None = None
        self._known: dict[str, tuple[str, str]] = {}  # schedule_id -> (cron, tz)

    async def start(self, *, on_fire: OnFire) -> None:
        self._on_fire = on_fire
        self._scheduler.start()
        logger.info("APScheduler iniciado")

    async def sync(self, specs: list[ScheduleSpec]) -> None:
        desired = {s.id: (s.cron, s.timezone) for s in specs}

        for schedule_id in list(self._known):
            if schedule_id not in desired:
                self._remove(schedule_id)

        for spec in specs:
            key = (spec.cron, spec.timezone)
            if self._known.get(spec.id) == key:
                continue
            self._add_or_replace(spec)

    async def shutdown(self) -> None:
        self._scheduler.shutdown(wait=False)

    # ── internos ───────────────────────────────────────────────────────────
    def _job_id(self, schedule_id: str) -> str:
        return f"{_JOB_PREFIX}{schedule_id}"

    def _add_or_replace(self, spec: ScheduleSpec) -> None:
        trigger = CronTrigger.from_crontab(spec.cron, timezone=spec.timezone)
        self._scheduler.add_job(
            self._fire,
            trigger=trigger,
            id=self._job_id(spec.id),
            args=[spec.id],
            replace_existing=True,
            misfire_grace_time=60,
            coalesce=True,
            max_instances=1,
        )
        self._known[spec.id] = (spec.cron, spec.timezone)
        logger.info("cron registrado", extra={"schedule_id": spec.id, "cron": spec.cron})

    def _remove(self, schedule_id: str) -> None:
        with contextlib.suppress(Exception):  # job pode já não existir
            self._scheduler.remove_job(self._job_id(schedule_id))
        self._known.pop(schedule_id, None)
        logger.info("cron removido", extra={"schedule_id": schedule_id})

    async def _fire(self, schedule_id: str) -> None:
        if self._on_fire is None:  # pragma: no cover
            return
        try:
            await self._on_fire(schedule_id)
        except Exception:
            logger.exception("erro ao disparar schedule", extra={"schedule_id": schedule_id})
