"""Git local do Workspace único (`/root`): status / diff / log / branches /
commit / checkout / discard + remoto GitHub (remote link / push / pull /
merge abort — usa o PAT do usuário conectado em `/api/github`, ver
`services/github/account_service.py`).
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
    GitPullRead,
    GitPushResult,
    GitRemoteLinkRequest,
    GitStatusRead,
)
from nbplatform.services.audit_service import AuditService
from nbplatform.services.git_service import GitService
from nbplatform.services.github import account_service as github_account_service
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


def _remote_url(repo_full_name: str) -> str:
    # sem credenciais na URL — o PAT vai só no header de auth por chamada
    # (`GitService._run_authed`), nunca gravado em `.git/config`.
    return f"https://github.com/{repo_full_name}.git"


@router.post("/remote", response_model=GitPullRead, status_code=status.HTTP_201_CREATED)
async def git_remote_link(
    payload: GitRemoteLinkRequest,
    session: SessionDep,
    access: WorkspaceEditor,
) -> GitPullRead:
    """"Inicializar Repositório no Workspace": vincula o repo GitHub escolhido
    e traz seu conteúdo pro Workspace (clone/merge inicial)."""
    await github_account_service.link_repo(
        session,
        access.user.id,
        repo_full_name=payload.repo_full_name,
        default_branch=payload.branch,
        base_dir=payload.base_dir,
    )
    _, token = await github_account_service.require_account_and_token(session, access.user.id)
    result = await _svc(access.user.id).init_from_remote(
        token,
        _remote_url(payload.repo_full_name),
        payload.branch,
        author_name=access.user.name or "",
        author_email=access.user.email or "",
    )
    if not result.conflicts:
        await github_account_service.mark_synced(session, access.user.id)
    await _audit(
        session,
        access.user.id,
        "WORKSPACE_GIT_REMOTE_LINK",
        repo=payload.repo_full_name,
        branch=payload.branch,
        conflicts=len(result.conflicts),
    )
    return GitPullRead(conflicts=result.conflicts)


@router.post("/push", response_model=GitPushResult)
async def git_push(session: SessionDep, access: WorkspaceEditor) -> GitPushResult:
    account, token = await github_account_service.require_account_and_token(
        session, access.user.id
    )
    svc = _svc(access.user.id)
    st = await svc.status()
    branch = st.branch or account.repo_default_branch or "main"
    await svc.push(token, branch)
    await github_account_service.mark_synced(session, access.user.id)
    await _audit(session, access.user.id, "WORKSPACE_GIT_PUSH", branch=branch)
    return GitPushResult(branch=branch)


@router.post("/pull", response_model=GitPullRead)
async def git_pull(session: SessionDep, access: WorkspaceEditor) -> GitPullRead:
    account, token = await github_account_service.require_account_and_token(
        session, access.user.id
    )
    svc = _svc(access.user.id)
    st = await svc.status()
    branch = st.branch or account.repo_default_branch or "main"
    result = await svc.pull(token, branch)
    if not result.conflicts:
        await github_account_service.mark_synced(session, access.user.id)
    await _audit(
        session,
        access.user.id,
        "WORKSPACE_GIT_PULL",
        branch=branch,
        conflicts=len(result.conflicts),
    )
    return GitPullRead(conflicts=result.conflicts)


@router.post("/merge/abort")
async def git_merge_abort(session: SessionDep, access: WorkspaceEditor) -> dict[str, bool]:
    await _svc(access.user.id).abort_merge()
    await _audit(session, access.user.id, "WORKSPACE_GIT_MERGE_ABORT")
    return {"aborted": True}
