"""Secrets: cifrados em repouso, valor NUNCA sai da API."""

from __future__ import annotations

from functools import cached_property

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nbplatform.core.config import get_settings
from nbplatform.core.crypto import SecretCipher
from nbplatform.core.errors import NotFoundError
from nbplatform.models.config_vars import Secret


class SecretService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @cached_property
    def cipher(self) -> SecretCipher:
        return SecretCipher(get_settings().secret_encryption_key)

    async def upsert(self, key: str, value: str) -> Secret:
        secret = await self.session.scalar(select(Secret).where(Secret.key == key))
        if secret is None:
            secret = Secret(key=key, ciphertext=self.cipher.encrypt(value))
            self.session.add(secret)
        else:
            secret.ciphertext = self.cipher.encrypt(value)
        await self.session.flush()
        await self.session.refresh(secret)
        return secret

    async def list_keys(self) -> list[Secret]:
        return list(
            await self.session.scalars(select(Secret).order_by(Secret.key))
        )

    async def delete(self, key: str) -> None:
        secret = await self.session.scalar(select(Secret).where(Secret.key == key))
        if secret is None:
            raise NotFoundError(f"Secret {key!r} não encontrado.")
        await self.session.delete(secret)

    async def resolve_all(self) -> dict[str, str]:
        """Descriptografa todos os secrets (worker → injeta como env var)."""
        rows = list(await self.session.scalars(select(Secret)))
        if not rows:
            return {}
        out: dict[str, str] = {}
        for secret in rows:
            try:
                out[secret.key] = self.cipher.decrypt(secret.ciphertext)
            except ValueError:  # pragma: no cover - dado corrompido
                continue
        return out
