"""Seed idempotente. Fase 1: garante o usuário `dev` usado enquanto não há auth."""

from __future__ import annotations

import logging

from sqlalchemy import select

from nbplatform.db.session import session_scope
from nbplatform.models.user import User

logger = logging.getLogger(__name__)

DEV_USER_EMAIL = "dev@nbplatform.local"


async def ensure_dev_user() -> None:
    async with session_scope() as session:
        existing = await session.scalar(select(User).where(User.email == DEV_USER_EMAIL))
        if existing is None:
            session.add(User(email=DEV_USER_EMAIL, name="Dev User"))
            logger.info("seed: usuário dev criado", extra={"email": DEV_USER_EMAIL})
        else:
            logger.info("seed: usuário dev já existe")
