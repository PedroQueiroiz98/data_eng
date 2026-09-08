"""Autenticação: login, /me, registro (admin)."""

from __future__ import annotations

from fastapi import APIRouter, status

from nbplatform.api.deps import AdminUser, CurrentUser, SessionDep
from nbplatform.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserRead,
)
from nbplatform.services.audit_service import AuditService
from nbplatform.services.auth_service import AuthService

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, session: SessionDep) -> TokenResponse:
    user, token = await AuthService(session).login(email=payload.email, password=payload.password)
    await AuditService(session).record(
        user_id=user.id, action="LOGIN", resource_type="user", resource_id=str(user.id)
    )
    return TokenResponse(access_token=token, user=UserRead.model_validate(user))


@router.get("/me", response_model=UserRead)
async def me(user: CurrentUser) -> UserRead:
    return UserRead.model_validate(user)


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, session: SessionDep, admin: AdminUser) -> UserRead:
    user = await AuthService(session).register(
        email=payload.email,
        name=payload.name,
        password=payload.password,
        role=payload.role,
    )
    await AuditService(session).record(
        user_id=admin.id,
        action="CREATE_USER",
        resource_type="user",
        resource_id=str(user.id),
        metadata={"email": user.email, "role": user.role},
    )
    return UserRead.model_validate(user)
