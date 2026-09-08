"""Autenticação: login e resolução do usuário a partir do token."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from nbplatform.core.errors import DomainError, ForbiddenError
from nbplatform.core.security import create_access_token, hash_password, verify_password
from nbplatform.models.user import User
from nbplatform.repositories.user_repository import UserRepository

# ForbiddenError vive em core.errors; re-exportado aqui por compatibilidade
# (api/deps.py e outros importam de nbplatform.services.auth_service).
__all__ = ["AuthError", "ForbiddenError", "AuthService"]


class AuthError(DomainError):
    status_code = 401
    code = "unauthorized"


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = UserRepository(session)

    async def login(self, *, email: str, password: str) -> tuple[User, str]:
        user = await self.repo.get_by_email(email.lower().strip())
        if user is None or not verify_password(password, user.password_hash):
            raise AuthError("Credenciais inválidas.")
        token = create_access_token(subject=str(user.id), role=user.role)
        return user, token

    async def get_user(self, user_id: uuid.UUID) -> User | None:
        return await self.repo.get(user_id)

    async def register(self, *, email: str, name: str, password: str, role: str = "member") -> User:
        email = email.lower().strip()
        if await self.repo.get_by_email(email) is not None:
            raise DomainError("E-mail já cadastrado.")
        user = User(email=email, name=name, password_hash=hash_password(password), role=role)
        await self.repo.add(user)
        return user
