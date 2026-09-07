"""Endpoints de notificação: config por pipeline, settings global, histórico, retry."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, status

from nbplatform.api.deps import AdminUser, CurrentUserId, RedisDep, SessionDep
from nbplatform.repositories.notification_repository import NotificationRepository
from nbplatform.schemas.notification import (
    NotificationConfigRead,
    NotificationConfigUpdate,
    NotificationRead,
    NotificationSettingsRead,
    NotificationSettingsUpdate,
)
from nbplatform.services.audit_service import AuditService
from nbplatform.services.notifications import NotificationService
from nbplatform.services.notifications.admin import (
    get_config,
    get_settings_read,
    put_config,
    put_settings,
)

router = APIRouter(tags=["notifications"])


# ── config por Pipeline/Workflow ────────────────────────────────────────────
@router.get(
    "/api/workflows/{workflow_id}/notifications", response_model=NotificationConfigRead
)
async def read_workflow_notifications(
    workflow_id: uuid.UUID, session: SessionDep
) -> NotificationConfigRead:
    return await get_config(session, workflow_id)


@router.put(
    "/api/workflows/{workflow_id}/notifications", response_model=NotificationConfigRead
)
async def update_workflow_notifications(
    workflow_id: uuid.UUID,
    payload: NotificationConfigUpdate,
    session: SessionDep,
    user_id: CurrentUserId,
) -> NotificationConfigRead:
    result = await put_config(session, workflow_id, payload)
    await AuditService(session).record(
        user_id=user_id,
        action="UPDATE_NOTIFICATION_CONFIG",
        resource_type="workflow",
        resource_id=str(workflow_id),
    )
    return result


# ── settings globais (admin) ────────────────────────────────────────────────
@router.get("/api/notifications/settings", response_model=NotificationSettingsRead)
async def read_notification_settings(
    session: SessionDep, _admin: AdminUser
) -> NotificationSettingsRead:
    return await get_settings_read(session)


@router.put("/api/notifications/settings", response_model=NotificationSettingsRead)
async def update_notification_settings(
    payload: NotificationSettingsUpdate, session: SessionDep, admin: AdminUser
) -> NotificationSettingsRead:
    result = await put_settings(session, payload)
    await AuditService(session).record(
        user_id=admin.id,
        action="UPDATE_NOTIFICATION_SETTINGS",
        resource_type="notification_settings",
        resource_id="global",
    )
    return result


# ── histórico + retry ──────────────────────────────────────────────────────
@router.get("/api/jobs/{job_id}/notifications", response_model=list[NotificationRead])
async def job_notifications(job_id: uuid.UUID, session: SessionDep) -> list[NotificationRead]:
    rows = await NotificationRepository(session).for_job(job_id)
    return [NotificationRead.model_validate(r) for r in rows]


@router.post(
    "/api/notifications/{notification_id}/retry", status_code=status.HTTP_202_ACCEPTED
)
async def retry_notification(
    notification_id: uuid.UUID, redis: RedisDep, user_id: CurrentUserId, session: SessionDep
) -> dict[str, str]:
    await NotificationService(redis).retry(notification_id)
    await AuditService(session).record(
        user_id=user_id,
        action="RETRY_NOTIFICATION",
        resource_type="notification",
        resource_id=str(notification_id),
    )
    return {"status": "queued"}
