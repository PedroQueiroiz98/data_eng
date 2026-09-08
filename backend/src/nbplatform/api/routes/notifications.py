"""Endpoints da Central de Notificações: providers globais + histórico de envios."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query, status

from nbplatform.api.deps import AdminUser, CurrentUserId, RedisDep, SessionDep
from nbplatform.domain.notifications import (
    NotificationEventType,
    NotificationStatus,
)
from nbplatform.repositories.notification_repository import NotificationRepository
from nbplatform.schemas.notification import (
    NotificationDeliveryDetail,
    NotificationDeliveryPage,
    NotificationDeliveryRead,
    NotificationProviderCreate,
    NotificationProviderEnabledPatch,
    NotificationProviderRead,
    NotificationProviderUpdate,
    NotificationTestResult,
)
from nbplatform.services.audit_service import AuditService
from nbplatform.services.notifications import NotificationService
from nbplatform.services.notifications.provider_admin import (
    create_provider,
    delete_provider,
    get_provider,
    list_providers,
    set_enabled,
    test_provider,
    update_provider,
)

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


# ── providers ──────────────────────────────────────────────────────────────
@router.get("/providers", response_model=list[NotificationProviderRead])
async def get_providers(session: SessionDep) -> list[NotificationProviderRead]:
    return await list_providers(session)


@router.post(
    "/providers",
    response_model=NotificationProviderRead,
    status_code=status.HTTP_201_CREATED,
)
async def post_provider(
    payload: NotificationProviderCreate, session: SessionDep, admin: AdminUser
) -> NotificationProviderRead:
    result = await create_provider(session, payload)
    await AuditService(session).record(
        user_id=admin.id,
        action="CREATE_NOTIFICATION_PROVIDER",
        resource_type="notification_provider",
        resource_id=str(result.id),
        metadata={"provider_type": result.provider_type},
    )
    return result


@router.get("/providers/{provider_id}", response_model=NotificationProviderRead)
async def get_one_provider(provider_id: uuid.UUID, session: SessionDep) -> NotificationProviderRead:
    return await get_provider(session, provider_id)


@router.put("/providers/{provider_id}", response_model=NotificationProviderRead)
async def put_provider(
    provider_id: uuid.UUID,
    payload: NotificationProviderUpdate,
    session: SessionDep,
    admin: AdminUser,
) -> NotificationProviderRead:
    result = await update_provider(session, provider_id, payload)
    await AuditService(session).record(
        user_id=admin.id,
        action="UPDATE_NOTIFICATION_PROVIDER",
        resource_type="notification_provider",
        resource_id=str(provider_id),
    )
    return result


@router.delete("/providers/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
async def del_provider(provider_id: uuid.UUID, session: SessionDep, admin: AdminUser) -> None:
    await delete_provider(session, provider_id)
    await AuditService(session).record(
        user_id=admin.id,
        action="DELETE_NOTIFICATION_PROVIDER",
        resource_type="notification_provider",
        resource_id=str(provider_id),
    )


@router.patch("/providers/{provider_id}/enabled", response_model=NotificationProviderRead)
async def patch_provider_enabled(
    provider_id: uuid.UUID,
    payload: NotificationProviderEnabledPatch,
    session: SessionDep,
    admin: AdminUser,
) -> NotificationProviderRead:
    result = await set_enabled(session, provider_id, payload.enabled)
    await AuditService(session).record(
        user_id=admin.id,
        action="TOGGLE_NOTIFICATION_PROVIDER",
        resource_type="notification_provider",
        resource_id=str(provider_id),
        metadata={"enabled": payload.enabled},
    )
    return result


@router.post("/providers/{provider_id}/test", response_model=NotificationTestResult)
async def post_provider_test(
    provider_id: uuid.UUID, session: SessionDep, redis: RedisDep, admin: AdminUser
) -> NotificationTestResult:
    result = await test_provider(session, redis, provider_id)
    await AuditService(session).record(
        user_id=admin.id,
        action="TEST_NOTIFICATION_PROVIDER",
        resource_type="notification_provider",
        resource_id=str(provider_id),
        metadata={"ok": result.ok},
    )
    return result


# ── deliveries (histórico) ────────────────────────────────────────────────
@router.get("/deliveries", response_model=NotificationDeliveryPage)
async def get_deliveries(
    session: SessionDep,
    provider: Annotated[uuid.UUID | None, Query()] = None,
    status_: Annotated[NotificationStatus | None, Query(alias="status")] = None,
    event: Annotated[NotificationEventType | None, Query()] = None,
    workflow: Annotated[uuid.UUID | None, Query()] = None,
    job: Annotated[uuid.UUID | None, Query()] = None,
    environment: Annotated[str | None, Query()] = None,
    date_from: Annotated[datetime | None, Query()] = None,
    date_to: Annotated[datetime | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> NotificationDeliveryPage:
    rows, total = await NotificationRepository(session).list_deliveries(
        provider=provider,
        status=status_,
        event=event,
        workflow=workflow,
        job=job,
        environment=environment,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    return NotificationDeliveryPage(
        items=[NotificationDeliveryRead.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/deliveries/{delivery_id}", response_model=NotificationDeliveryDetail)
async def get_delivery(delivery_id: uuid.UUID, session: SessionDep) -> NotificationDeliveryDetail:
    from nbplatform.core.errors import NotFoundError

    row = await NotificationRepository(session).get_delivery(delivery_id)
    if row is None:
        raise NotFoundError(f"Delivery {delivery_id} não encontrada.")
    return NotificationDeliveryDetail.model_validate(row)


@router.post("/deliveries/{delivery_id}/retry", status_code=status.HTTP_202_ACCEPTED)
async def retry_delivery(
    delivery_id: uuid.UUID,
    redis: RedisDep,
    user_id: CurrentUserId,
    session: SessionDep,
) -> dict[str, str]:
    await NotificationService(redis).retry(delivery_id)
    await AuditService(session).record(
        user_id=user_id,
        action="RETRY_NOTIFICATION_DELIVERY",
        resource_type="notification_delivery",
        resource_id=str(delivery_id),
    )
    return {"status": "queued"}
