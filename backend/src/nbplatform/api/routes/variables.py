"""Variáveis: valores não-sensíveis, retornáveis."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Query, status
from pydantic import BaseModel, ConfigDict, Field

from nbplatform.api.deps import CurrentUser, SessionDep
from nbplatform.services.audit_service import AuditService
from nbplatform.services.variable_service import VariableService

router = APIRouter(prefix="/api/variables", tags=["variables"])


class VariableIn(BaseModel):
    value: str
    scope: str = Field(default="global", max_length=100)


class VariableRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: str
    value: str
    scope: str
    updated_at: datetime


@router.get("", response_model=list[VariableRead])
async def list_variables(session: SessionDep, user: CurrentUser) -> list[VariableRead]:
    return [VariableRead.model_validate(v) for v in await VariableService(session).list_all()]


@router.put("/{key}", response_model=VariableRead)
async def upsert_variable(
    key: str, payload: VariableIn, session: SessionDep, user: CurrentUser
) -> VariableRead:
    variable = await VariableService(session).upsert(key, payload.value, scope=payload.scope)
    await AuditService(session).record(
        user_id=user.id,
        action="UPSERT_VARIABLE",
        resource_type="variable",
        resource_id=f"{payload.scope}/{key}",
    )
    return VariableRead.model_validate(variable)


@router.delete("/{key}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_variable(
    key: str,
    session: SessionDep,
    user: CurrentUser,
    scope: str = Query(default="global"),
) -> None:
    await VariableService(session).delete(key, scope=scope)
    await AuditService(session).record(
        user_id=user.id,
        action="DELETE_VARIABLE",
        resource_type="variable",
        resource_id=f"{scope}/{key}",
    )
