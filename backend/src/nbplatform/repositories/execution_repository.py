"""Acesso a dados para Execution / ExecutionLog."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nbplatform.domain.enums import ExecutionStatus
from nbplatform.models.execution import Execution, ExecutionLog


class ExecutionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, execution: Execution) -> None:
        self.session.add(execution)
        await self.session.flush()

    async def get(self, execution_id: uuid.UUID) -> Execution | None:
        return await self.session.get(Execution, execution_id)

    async def get_for_update(self, execution_id: uuid.UUID) -> Execution | None:
        stmt = select(Execution).where(Execution.id == execution_id).with_for_update()
        return await self.session.scalar(stmt)

    async def get_by_idempotency_key(self, key: str) -> Execution | None:
        stmt = select(Execution).where(Execution.idempotency_key == key)
        return await self.session.scalar(stmt)

    async def list_paged(
        self,
        *,
        limit: int,
        offset: int,
        status: ExecutionStatus | None = None,
        notebook_version_id: uuid.UUID | None = None,
    ) -> list[Execution]:
        stmt = select(Execution).order_by(Execution.created_at.desc())
        if status is not None:
            stmt = stmt.where(Execution.status == status)
        if notebook_version_id is not None:
            stmt = stmt.where(Execution.notebook_version_id == notebook_version_id)
        stmt = stmt.limit(limit).offset(offset)
        return list(await self.session.scalars(stmt))

    async def add_log(self, log: ExecutionLog) -> None:
        self.session.add(log)
        await self.session.flush()

    async def logs_since(
        self, execution_id: uuid.UUID, *, after_seq: int = 0
    ) -> list[ExecutionLog]:
        stmt = (
            select(ExecutionLog)
            .where(
                ExecutionLog.execution_id == execution_id,
                ExecutionLog.seq > after_seq,
            )
            .order_by(ExecutionLog.seq)
        )
        return list(await self.session.scalars(stmt))
