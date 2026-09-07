"""Listagem de audit logs (admin)."""

from __future__ import annotations

from fastapi import APIRouter, Query

from nbplatform.api.deps import AdminUser, SessionDep
from nbplatform.schemas.auth import AuditLogRead
from nbplatform.services.audit_service import AuditService

router = APIRouter(prefix="/api/audit-logs", tags=["audit"])


@router.get("", response_model=list[AuditLogRead])
async def list_audit_logs(
    session: SessionDep,
    admin: AdminUser,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[AuditLogRead]:
    logs = await AuditService(session).list_recent(limit=limit, offset=offset)
    return [AuditLogRead.model_validate(log) for log in logs]
