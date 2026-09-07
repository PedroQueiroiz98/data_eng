"""Acesso a dados de notificação (config por workflow, settings global, histórico)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from nbplatform.domain.notifications import (
    NotificationChannel,
    NotificationEvent,
    NotificationStatus,
)
from nbplatform.models.notification import (
    Notification,
    NotificationConfig,
    NotificationSettings,
)


class NotificationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ── config por workflow ────────────────────────────────────────────────
    async def get_config(self, workflow_id: uuid.UUID) -> NotificationConfig | None:
        return await self.session.scalar(
            select(NotificationConfig).where(
                NotificationConfig.workflow_id == workflow_id
            )
        )

    async def upsert_config(self, workflow_id: uuid.UUID) -> NotificationConfig:
        cfg = await self.get_config(workflow_id)
        if cfg is None:
            cfg = NotificationConfig(workflow_id=workflow_id)
            self.session.add(cfg)
            await self.session.flush()
        return cfg

    # ── settings global (linha única) ─────────────────────────────────────
    async def get_settings_row(self) -> NotificationSettings | None:
        return await self.session.scalar(
            select(NotificationSettings).order_by(NotificationSettings.created_at).limit(1)
        )

    async def upsert_settings_row(self) -> NotificationSettings:
        row = await self.get_settings_row()
        if row is None:
            row = NotificationSettings()
            self.session.add(row)
            await self.session.flush()
        return row

    # ── histórico ─────────────────────────────────────────────────────────
    async def create_if_absent(
        self,
        *,
        job_id: uuid.UUID,
        workflow_id: uuid.UUID | None,
        execution_id: uuid.UUID | None,
        channel: NotificationChannel,
        event_type: NotificationEvent,
        recipient: str | None,
        max_attempts: int,
        payload: dict[str, Any],
        seq: int,
    ) -> uuid.UUID | None:
        """INSERT idempotente por (job_id, event_type, channel). None se já existe."""
        stmt = (
            pg_insert(Notification)
            .values(
                job_id=job_id,
                workflow_id=workflow_id,
                execution_id=execution_id,
                channel=channel,
                event_type=event_type,
                status=NotificationStatus.PENDING,
                recipient=recipient,
                attempt=0,
                max_attempts=max_attempts,
                payload=payload,
                seq=seq,
            )
            .on_conflict_do_nothing(constraint="uq_notification_idempotency")
            .returning(Notification.id)
        )
        return await self.session.scalar(stmt)

    async def get(self, notification_id: uuid.UUID) -> Notification | None:
        return await self.session.get(Notification, notification_id)

    async def for_job(self, job_id: uuid.UUID) -> list[Notification]:
        return list(
            await self.session.scalars(
                select(Notification)
                .where(Notification.job_id == job_id)
                .order_by(Notification.created_at)
            )
        )
