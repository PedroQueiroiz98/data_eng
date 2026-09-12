"""Secrets: gestão. O VALOR nunca é retornado."""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, status
from pydantic import BaseModel, ConfigDict, Field

from nbplatform.api.deps import AdminUser, RedisDep, SessionDep
from nbplatform.services.audit_service import AuditService
from nbplatform.services.secret_service import SecretService
from nbplatform.ws.events import publish_config_event

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/secrets", tags=["secrets"])


class SecretValueIn(BaseModel):
    value: str = Field(min_length=1)


class SecretMeta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: str
    created_at: datetime
    updated_at: datetime


@router.get("", response_model=list[SecretMeta])
async def list_secrets(session: SessionDep, admin: AdminUser) -> list[SecretMeta]:
    return [SecretMeta.model_validate(s) for s in await SecretService(session).list_keys()]


@router.put("/{key}", response_model=SecretMeta, status_code=status.HTTP_200_OK)
async def upsert_secret(
    key: str, payload: SecretValueIn, session: SessionDep, admin: AdminUser, redis: RedisDep
) -> SecretMeta:
    secret = await SecretService(session).upsert(key, payload.value)
    await AuditService(session).record(
        user_id=admin.id, action="UPSERT_SECRET", resource_type="secret", resource_id=key
    )
    # commit explícito: o kernel-worker reage ao evento abrindo sua PRÓPRIA
    # sessão de banco — sem isso, ele pode reler o valor antes do commit ficar
    # visível (o commit "automático" do SessionDep só roda no teardown da
    # dependência, depois que esta função já retornou).
    await session.commit()
    try:
        await publish_config_event(redis, {"type": "secret_changed", "key": key, "op": "upsert"})
    except Exception:  # noqa: BLE001
        logger.warning("falha ao publicar secret_changed para %s", key, exc_info=True)
    return SecretMeta.model_validate(secret)


@router.delete("/{key}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_secret(key: str, session: SessionDep, admin: AdminUser, redis: RedisDep) -> None:
    await SecretService(session).delete(key)
    await AuditService(session).record(
        user_id=admin.id, action="DELETE_SECRET", resource_type="secret", resource_id=key
    )
    await session.commit()
    try:
        await publish_config_event(redis, {"type": "secret_changed", "key": key, "op": "delete"})
    except Exception:  # noqa: BLE001
        logger.warning("falha ao publicar secret_changed para %s", key, exc_info=True)
