"""Acesso a dados do assistente de IA (providers globais + histórico)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Select, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from nbplatform.models.assistant import AssistantInteraction, AssistantProvider


class AssistantRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ── providers ────────────────────────────────────────────────────────
    async def list_providers(self) -> list[AssistantProvider]:
        return list(
            await self.session.scalars(
                select(AssistantProvider).order_by(AssistantProvider.name)
            )
        )

    async def enabled_providers(self) -> list[AssistantProvider]:
        return list(
            await self.session.scalars(
                select(AssistantProvider)
                .where(AssistantProvider.enabled.is_(True))
                .order_by(AssistantProvider.is_default.desc(), AssistantProvider.name)
            )
        )

    async def default_provider(self) -> AssistantProvider | None:
        row = await self.session.scalar(
            select(AssistantProvider).where(
                AssistantProvider.enabled.is_(True),
                AssistantProvider.is_default.is_(True),
            )
        )
        if row is not None:
            return row
        # sem default explícito → o primeiro habilitado
        return await self.session.scalar(
            select(AssistantProvider)
            .where(AssistantProvider.enabled.is_(True))
            .order_by(AssistantProvider.name)
            .limit(1)
        )

    async def get_provider(self, provider_id: uuid.UUID) -> AssistantProvider | None:
        return await self.session.get(AssistantProvider, provider_id)

    async def name_exists(self, name: str, *, exclude: uuid.UUID | None = None) -> bool:
        stmt = select(AssistantProvider.id).where(AssistantProvider.name == name)
        if exclude is not None:
            stmt = stmt.where(AssistantProvider.id != exclude)
        return (await self.session.scalar(stmt)) is not None

    async def clear_default(self, *, exclude: uuid.UUID | None = None) -> None:
        stmt = update(AssistantProvider).values(is_default=False)
        if exclude is not None:
            stmt = stmt.where(AssistantProvider.id != exclude)
        await self.session.execute(stmt)

    # ── histórico ────────────────────────────────────────────────────────
    async def create_interaction(self, **fields: Any) -> uuid.UUID:
        row = AssistantInteraction(**fields)
        self.session.add(row)
        await self.session.flush()
        return row.id

    async def list_interactions(
        self,
        user_id: uuid.UUID,
        *,
        task: str | None = None,
        notebook_path: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[AssistantInteraction], int]:
        def apply(stmt: Select[Any]) -> Select[Any]:
            stmt = stmt.where(AssistantInteraction.user_id == user_id)
            if task:
                stmt = stmt.where(AssistantInteraction.task == task)
            if notebook_path:
                stmt = stmt.where(AssistantInteraction.notebook_path == notebook_path)
            return stmt

        rows = list(
            await self.session.scalars(
                apply(select(AssistantInteraction))
                .order_by(AssistantInteraction.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
        )
        total = int(
            await self.session.scalar(
                apply(select(func.count()).select_from(AssistantInteraction))
            )
            or 0
        )
        return rows, total

    async def get_interaction(
        self, interaction_id: uuid.UUID
    ) -> AssistantInteraction | None:
        return await self.session.get(AssistantInteraction, interaction_id)
