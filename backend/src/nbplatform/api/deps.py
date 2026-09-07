"""Dependências compartilhadas das rotas.

Auth real chega na Fase 8; por ora `current_user_id` devolve o id do usuário `dev`.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nbplatform.db.session import session_scope
from nbplatform.models.user import User
from nbplatform.queue.redis_client import get_redis
from nbplatform.services.seed import DEV_USER_EMAIL


async def get_session() -> AsyncIterator[AsyncSession]:
    async with session_scope() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]


def _redis() -> Redis:
    return get_redis()


RedisDep = Annotated[Redis, Depends(_redis)]


async def get_current_user_id(session: SessionDep) -> uuid.UUID | None:
    return await session.scalar(select(User.id).where(User.email == DEV_USER_EMAIL))


CurrentUserId = Annotated[uuid.UUID | None, Depends(get_current_user_id)]
