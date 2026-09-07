"""Dependências compartilhadas das rotas: sessão, redis, auth."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Annotated

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from nbplatform.db.session import session_scope
from nbplatform.models.user import User
from nbplatform.queue.redis_client import get_redis
from nbplatform.services.auth_service import AuthError, AuthService, ForbiddenError


async def get_session() -> AsyncIterator[AsyncSession]:
    async with session_scope() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]


def _redis() -> Redis:
    return get_redis()


RedisDep = Annotated[Redis, Depends(_redis)]

_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    session: SessionDep,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    if creds is None:
        raise AuthError("Token ausente.")
    try:
        from nbplatform.core.security import decode_access_token

        payload = decode_access_token(creds.credentials)
        user_id = uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise AuthError("Token inválido ou expirado.") from exc

    user = await AuthService(session).get_user(user_id)
    if user is None:
        raise AuthError("Usuário não encontrado.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_current_user_id(user: CurrentUser) -> uuid.UUID:
    return user.id


CurrentUserId = Annotated[uuid.UUID, Depends(get_current_user_id)]


async def require_admin(user: CurrentUser) -> User:
    if user.role != "admin":
        raise ForbiddenError("Ação restrita a administradores.")
    return user


AdminUser = Annotated[User, Depends(require_admin)]
