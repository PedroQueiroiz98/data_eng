"""Variáveis: valores não-sensíveis, retornáveis pela API, injetadas na execução."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nbplatform.core.errors import NotFoundError
from nbplatform.models.config_vars import Variable


class VariableService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert(self, key: str, value: str, *, scope: str = "global") -> Variable:
        stmt = select(Variable).where(Variable.key == key, Variable.scope == scope)
        variable = await self.session.scalar(stmt)
        if variable is None:
            variable = Variable(key=key, value=value, scope=scope)
            self.session.add(variable)
        else:
            variable.value = value
        await self.session.flush()
        await self.session.refresh(variable)
        return variable

    async def list_all(self) -> list[Variable]:
        return list(
            await self.session.scalars(
                select(Variable).order_by(Variable.scope, Variable.key)
            )
        )

    async def delete(self, key: str, *, scope: str = "global") -> None:
        stmt = select(Variable).where(Variable.key == key, Variable.scope == scope)
        variable = await self.session.scalar(stmt)
        if variable is None:
            raise NotFoundError(f"Variável {key!r} (scope {scope}) não encontrada.")
        await self.session.delete(variable)

    async def resolve(self, scope: str = "global") -> dict[str, str]:
        stmt = select(Variable).where(Variable.scope == scope)
        return {v.key: v.value for v in await self.session.scalars(stmt)}
