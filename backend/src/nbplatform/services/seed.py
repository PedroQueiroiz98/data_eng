"""Seed idempotente: garante o usuário admin (credenciais vêm do ambiente)."""

from __future__ import annotations

import logging

from sqlalchemy import select

from nbplatform.core.config import get_settings
from nbplatform.core.security import hash_password
from nbplatform.db.session import session_scope
from nbplatform.models.user import User

logger = logging.getLogger(__name__)


async def ensure_admin_user() -> None:
    settings = get_settings()
    email = settings.admin_email.lower().strip()
    async with session_scope() as session:
        existing = await session.scalar(select(User).where(User.email == email))
        if existing is None:
            session.add(
                User(
                    email=email,
                    name="Administrador",
                    role="admin",
                    password_hash=hash_password(settings.admin_password),
                )
            )
            logger.info("seed: usuário admin criado", extra={"email": email})
        elif existing.password_hash is None:
            existing.password_hash = hash_password(settings.admin_password)
            existing.role = "admin"
            logger.info("seed: senha do admin definida", extra={"email": email})
        else:
            logger.info("seed: usuário admin já existe")
