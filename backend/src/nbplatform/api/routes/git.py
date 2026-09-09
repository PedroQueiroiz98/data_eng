"""Git local do Workspace único (`/root`): status / diff / log / branches / commit / checkout.

Sem remoto (push/pull/clone) nesta rodada.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Query, status

from nbplatform.api.deps import SessionDep, WorkspaceEditor, WorkspaceViewer
from nbplatform.core.config import get_settings
from nbplatform.schemas.git import (
    GitBranchCreate,
    GitBranchesRead,
    GitCheckoutRequest,
    GitCommitRead,
    GitCommitRequest,
    GitCommitResult,
    GitDiffRead,
    GitDiscardRequest,
    GitStatusRead,
)
from nbplatform.services.audit_service import AuditService
from nbplatform.services.git_service import GitService
from nbplatform.services.workspace_service import SINGLETON_WORKSPACE_ID

router = APIRouter(prefix="/api/workspace/git", tags=["git"])

_WID = SINGLETON_WORKSPACE_ID


def _svc(user_id: uuid.UUID) -> GitService:
    return GitService(Path(get_settings().workspace_dir) / str(user_id))


async def _audit(
    session: SessionDep, user_id: uuid.UUID, action: str, **meta: object
) -> None:
    await AuditService(session).record(
        user_id=user_id,
        action=action,
        resource_type="workspace",
        resource_id=str(_WID),
        metadata={k: str(v) for k, v in meta.items()} or None,
    )


@router.get("/status", response_model=GitStatusRead)
async def git_status(access: WorkspaceViewer) -> GitStatusRead:
    result = await _svc(access.user.id).status()
    return GitStatusRead.model_validate(result, from_attributes=True)


@router.get("/diff", response_model=GitDiffRead)
async def git_diff(
    access: WorkspaceViewer,
    path: str | None = Query(default=None),
) -> GitDiffRead:
    diff = await _svc(access.user.id).diff(path)
    return GitDiffRead(path=path, diff=diff)


@router.get("/log", response_model=list[GitCommitRead])
async def git_log(
    access: WorkspaceViewer,
    limit: int = Query(default=50, ge=1, le=500),
) -> list[GitCommitRead]:
    commits = await _svc(access.user.id).log(limit)
    return [GitCommitRead.model_validate(c, from_attributes=True) for c in commits]


@router.get("/branches", response_model=GitBranchesRead)
async def git_branches(access: WorkspaceViewer) -> GitBranchesRead:
    svc = _svc(access.user.id)
    st = await svc.status()
    return GitBranchesRead(current=st.branch, branches=await svc.branches())


@router.post("/init", response_model=GitStatusRead, status_code=status.HTTP_201_CREATED)
async def git_init(session: SessionDep, access: WorkspaceEditor) -> GitStatusRead:
    svc = _svc(access.user.id)
    await svc.ensure_repo(
        author_name=access.user.name or "",
        author_email=access.user.email or "",
    )
    await _audit(session, access.user.id, "WORKSPACE_GIT_INIT")
    return GitStatusRead.model_validate(await svc.status(), from_attributes=True)


@router.post("/branches", status_code=status.HTTP_201_CREATED)
async def git_create_branch(
    payload: GitBranchCreate,
    session: SessionDep,
    access: WorkspaceEditor,
) -> dict[str, str]:
    await _svc(access.user.id).create_branch(payload.name)
    await _audit(session, access.user.id, "WORKSPACE_GIT_BRANCH", name=payload.name)
    return {"branch": payload.name}


@router.post("/checkout")
async def git_checkout(
    payload: GitCheckoutRequest,
    session: SessionDep,
    access: WorkspaceEditor,
) -> dict[str, str]:
    await _svc(access.user.id).checkout(payload.ref)
    await _audit(session, access.user.id, "WORKSPACE_GIT_CHECKOUT", ref=payload.ref)
    return {"ref": payload.ref}


@router.post("/commit", response_model=GitCommitResult)
async def git_commit(
    payload: GitCommitRequest,
    session: SessionDep,
    access: WorkspaceEditor,
) -> GitCommitResult:
    sha = await _svc(access.user.id).commit(
        paths=payload.paths,
        message=payload.message,
        author_name=access.user.name or "",
        author_email=access.user.email or "",
    )
    await _audit(session, access.user.id, "WORKSPACE_GIT_COMMIT", sha=sha)
    return GitCommitResult(sha=sha)


@router.post("/discard")
async def git_discard(
    payload: GitDiscardRequest,
    session: SessionDep,
    access: WorkspaceEditor,
) -> dict[str, int]:
    await _svc(access.user.id).discard(payload.paths)
    await _audit(session, access.user.id, "WORKSPACE_GIT_DISCARD", count=len(payload.paths))
    return {"discarded": len(payload.paths)}
