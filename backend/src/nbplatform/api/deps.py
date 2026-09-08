"""Dependências compartilhadas das rotas: sessão, redis, auth, ACL de Workspace."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from nbplatform.db.session import session_scope
from nbplatform.domain.enums import WORKSPACE_ROLE_RANK, WorkspaceRole
from nbplatform.models.user import User
from nbplatform.queue.redis_client import get_redis
from nbplatform.repositories.workspace_repository import WorkspaceRepository
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


# ── ACL de Workspace ────────────────────────────────────────────────────────
@dataclass(frozen=True)
class WorkspaceAccess:
    """Resultado de `require_workspace_role`: quem é e com que papel efetivo."""

    user: User
    role: WorkspaceRole
    is_admin: bool


def require_workspace_role(
    minimum: WorkspaceRole,
) -> Callable[..., Awaitable[WorkspaceAccess]]:
    """Dependency que exige papel >= `minimum` no Workspace da rota (path `workspace_id`).

    Admin global tem bypass (papel efetivo OWNER). Não-membro → 403.
    """

    async def _dep(
        workspace_id: uuid.UUID, user: CurrentUser, session: SessionDep
    ) -> WorkspaceAccess:
        if user.role == "admin":
            return WorkspaceAccess(user=user, role=WorkspaceRole.OWNER, is_admin=True)
        member = await WorkspaceRepository(session).get_member(workspace_id, user.id)
        if member is None or (WORKSPACE_ROLE_RANK[member.role] < WORKSPACE_ROLE_RANK[minimum]):
            raise ForbiddenError("Sem permissão neste Workspace.")
        return WorkspaceAccess(user=user, role=member.role, is_admin=False)

    return _dep


WorkspaceViewer = Annotated[WorkspaceAccess, Depends(require_workspace_role(WorkspaceRole.VIEWER))]
WorkspaceEditor = Annotated[WorkspaceAccess, Depends(require_workspace_role(WorkspaceRole.EDITOR))]
WorkspaceOwner = Annotated[WorkspaceAccess, Depends(require_workspace_role(WorkspaceRole.OWNER))]
