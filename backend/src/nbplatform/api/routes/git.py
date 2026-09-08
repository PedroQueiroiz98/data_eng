"""Git local do Workspace: status / diff / log / branches / commit / checkout.

Sem remoto (push/pull/clone) nesta rodada.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, status

from nbplatform.api.deps import SessionDep, WorkspaceEditor, WorkspaceViewer
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
from nbplatform.services.workspace_service import WorkspaceService

router = APIRouter(prefix="/api/workspaces/{workspace_id}/git", tags=["git"])


def _svc(session: SessionDep, workspace_id: uuid.UUID) -> GitService:
    return GitService(WorkspaceService(session).root_for(workspace_id))


async def _audit(
    session: SessionDep, user_id: uuid.UUID, action: str, wid: uuid.UUID, **meta: object
) -> None:
    await AuditService(session).record(
        user_id=user_id,
        action=action,
        resource_type="workspace",
        resource_id=str(wid),
        metadata={k: str(v) for k, v in meta.items()} or None,
    )


@router.get("/status", response_model=GitStatusRead)
async def git_status(
    workspace_id: uuid.UUID, session: SessionDep, _access: WorkspaceViewer
) -> GitStatusRead:
    await WorkspaceService(session).get(workspace_id)
    result = await _svc(session, workspace_id).status()
    return GitStatusRead.model_validate(result, from_attributes=True)


@router.get("/diff", response_model=GitDiffRead)
async def git_diff(
    workspace_id: uuid.UUID,
    session: SessionDep,
    _access: WorkspaceViewer,
    path: str | None = Query(default=None),
) -> GitDiffRead:
    await WorkspaceService(session).get(workspace_id)
    diff = await _svc(session, workspace_id).diff(path)
    return GitDiffRead(path=path, diff=diff)


@router.get("/log", response_model=list[GitCommitRead])
async def git_log(
    workspace_id: uuid.UUID,
    session: SessionDep,
    _access: WorkspaceViewer,
    limit: int = Query(default=50, ge=1, le=500),
) -> list[GitCommitRead]:
    await WorkspaceService(session).get(workspace_id)
    commits = await _svc(session, workspace_id).log(limit)
    return [GitCommitRead.model_validate(c, from_attributes=True) for c in commits]


@router.get("/branches", response_model=GitBranchesRead)
async def git_branches(
    workspace_id: uuid.UUID, session: SessionDep, _access: WorkspaceViewer
) -> GitBranchesRead:
    await WorkspaceService(session).get(workspace_id)
    svc = _svc(session, workspace_id)
    st = await svc.status()
    return GitBranchesRead(current=st.branch, branches=await svc.branches())


@router.post("/init", response_model=GitStatusRead, status_code=status.HTTP_201_CREATED)
async def git_init(
    workspace_id: uuid.UUID, session: SessionDep, access: WorkspaceEditor
) -> GitStatusRead:
    await WorkspaceService(session).get_active(workspace_id)
    svc = _svc(session, workspace_id)
    await svc.ensure_repo(
        author_name=access.user.name or "",
        author_email=access.user.email or "",
    )
    await _audit(session, access.user.id, "WORKSPACE_GIT_INIT", workspace_id)
    return GitStatusRead.model_validate(await svc.status(), from_attributes=True)


@router.post("/branches", status_code=status.HTTP_201_CREATED)
async def git_create_branch(
    workspace_id: uuid.UUID,
    payload: GitBranchCreate,
    session: SessionDep,
    access: WorkspaceEditor,
) -> dict[str, str]:
    await WorkspaceService(session).get_active(workspace_id)
    await _svc(session, workspace_id).create_branch(payload.name)
    await _audit(session, access.user.id, "WORKSPACE_GIT_BRANCH", workspace_id, name=payload.name)
    return {"branch": payload.name}


@router.post("/checkout")
async def git_checkout(
    workspace_id: uuid.UUID,
    payload: GitCheckoutRequest,
    session: SessionDep,
    access: WorkspaceEditor,
) -> dict[str, str]:
    await WorkspaceService(session).get_active(workspace_id)
    await _svc(session, workspace_id).checkout(payload.ref)
    await _audit(session, access.user.id, "WORKSPACE_GIT_CHECKOUT", workspace_id, ref=payload.ref)
    return {"ref": payload.ref}


@router.post("/commit", response_model=GitCommitResult)
async def git_commit(
    workspace_id: uuid.UUID,
    payload: GitCommitRequest,
    session: SessionDep,
    access: WorkspaceEditor,
) -> GitCommitResult:
    await WorkspaceService(session).get_active(workspace_id)
    sha = await _svc(session, workspace_id).commit(
        paths=payload.paths,
        message=payload.message,
        author_name=access.user.name or "",
        author_email=access.user.email or "",
    )
    await _audit(session, access.user.id, "WORKSPACE_GIT_COMMIT", workspace_id, sha=sha)
    return GitCommitResult(sha=sha)


@router.post("/discard")
async def git_discard(
    workspace_id: uuid.UUID,
    payload: GitDiscardRequest,
    session: SessionDep,
    access: WorkspaceEditor,
) -> dict[str, int]:
    await WorkspaceService(session).get_active(workspace_id)
    await _svc(session, workspace_id).discard(payload.paths)
    await _audit(
        session,
        access.user.id,
        "WORKSPACE_GIT_DISCARD",
        workspace_id,
        count=len(payload.paths),
    )
    return {"discarded": len(payload.paths)}
