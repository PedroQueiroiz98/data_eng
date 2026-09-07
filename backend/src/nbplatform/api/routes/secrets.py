"""Secrets: gestão. O VALOR nunca é retornado."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, status
from pydantic import BaseModel, ConfigDict, Field

from nbplatform.api.deps import AdminUser, SessionDep
from nbplatform.services.audit_service import AuditService
from nbplatform.services.secret_service import SecretService

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
    key: str, payload: SecretValueIn, session: SessionDep, admin: AdminUser
) -> SecretMeta:
    secret = await SecretService(session).upsert(key, payload.value)
    await AuditService(session).record(
        user_id=admin.id, action="UPSERT_SECRET", resource_type="secret", resource_id=key
    )
    return SecretMeta.model_validate(secret)


@router.delete("/{key}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_secret(key: str, session: SessionDep, admin: AdminUser) -> None:
    await SecretService(session).delete(key)
    await AuditService(session).record(
        user_id=admin.id, action="DELETE_SECRET", resource_type="secret", resource_id=key
    )
