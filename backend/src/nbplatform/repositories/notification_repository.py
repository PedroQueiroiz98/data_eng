"""Acesso a dados da Central de Notificações (providers globais + deliveries)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from nbplatform.domain.notifications import (
    NotificationEventType,
    NotificationProviderType,
    NotificationStatus,
)
from nbplatform.models.notification import NotificationDelivery, NotificationProvider


class NotificationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ── providers ────────────────────────────────────────────────────────
    async def list_providers(self) -> list[NotificationProvider]:
        return list(
            await self.session.scalars(
                select(NotificationProvider).order_by(NotificationProvider.name)
            )
        )

    async def enabled_providers(self) -> list[NotificationProvider]:
        return list(
            await self.session.scalars(
                select(NotificationProvider)
                .where(NotificationProvider.enabled.is_(True))
                .order_by(NotificationProvider.name)
            )
        )

    async def get_provider(self, provider_id: uuid.UUID) -> NotificationProvider | None:
        return await self.session.get(NotificationProvider, provider_id)

    async def name_exists(self, name: str, *, exclude: uuid.UUID | None = None) -> bool:
        stmt = select(NotificationProvider.id).where(NotificationProvider.name == name)
        if exclude is not None:
            stmt = stmt.where(NotificationProvider.id != exclude)
        return (await self.session.scalar(stmt)) is not None

    # ── deliveries ───────────────────────────────────────────────────────
    async def create_if_absent(
        self,
        *,
        notification_provider_id: uuid.UUID,
        provider_type: NotificationProviderType,
        event_type: NotificationEventType,
        workflow_id: uuid.UUID | None,
        job_id: uuid.UUID | None,
        execution_id: uuid.UUID | None,
        dedupe_key: str,
        recipient: str | None,
        max_attempts: int,
        payload: dict[str, Any],
        seq: int,
    ) -> uuid.UUID | None:
        """INSERT idempotente por `dedupe_key`. None se já existe."""
        stmt = (
            pg_insert(NotificationDelivery)
            .values(
                notification_provider_id=notification_provider_id,
                provider_type=provider_type,
                event_type=event_type,
                workflow_id=workflow_id,
                job_id=job_id,
                execution_id=execution_id,
                status=NotificationStatus.PENDING,
                attempt=0,
                max_attempts=max_attempts,
                dedupe_key=dedupe_key,
                recipient=recipient,
                payload=payload,
                seq=seq,
            )
            .on_conflict_do_nothing(constraint="uq_notification_delivery_dedupe")
            .returning(NotificationDelivery.id)
        )
        return await self.session.scalar(stmt)

    async def get_delivery(self, delivery_id: uuid.UUID) -> NotificationDelivery | None:
        return await self.session.get(NotificationDelivery, delivery_id)

    async def deliveries_for_job(self, job_id: uuid.UUID) -> list[NotificationDelivery]:
        return list(
            await self.session.scalars(
                select(NotificationDelivery)
                .where(NotificationDelivery.job_id == job_id)
                .order_by(NotificationDelivery.created_at)
            )
        )

    async def list_deliveries(
        self,
        *,
        provider: uuid.UUID | None = None,
        status: NotificationStatus | None = None,
        event: NotificationEventType | None = None,
        workflow: uuid.UUID | None = None,
        job: uuid.UUID | None = None,
        environment: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[NotificationDelivery], int]:
        def apply(stmt: Select[Any]) -> Select[Any]:
            if provider is not None:
                stmt = stmt.where(NotificationDelivery.notification_provider_id == provider)
            if status is not None:
                stmt = stmt.where(NotificationDelivery.status == status)
            if event is not None:
                stmt = stmt.where(NotificationDelivery.event_type == event)
            if workflow is not None:
                stmt = stmt.where(NotificationDelivery.workflow_id == workflow)
            if job is not None:
                stmt = stmt.where(NotificationDelivery.job_id == job)
            if environment:
                stmt = stmt.where(NotificationDelivery.payload["environment"].astext == environment)
            if date_from is not None:
                stmt = stmt.where(NotificationDelivery.created_at >= date_from)
            if date_to is not None:
                stmt = stmt.where(NotificationDelivery.created_at <= date_to)
            return stmt

        rows = list(
            await self.session.scalars(
                apply(select(NotificationDelivery))
                .order_by(NotificationDelivery.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
        )
        total = int(
            await self.session.scalar(apply(select(func.count()).select_from(NotificationDelivery)))
            or 0
        )
        return rows, total
