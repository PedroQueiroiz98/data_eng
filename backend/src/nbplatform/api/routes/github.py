"""Integração GitHub: conta pessoal do usuário (PAT), repositórios, branches.

O vínculo repo/branch/base_dir e a sincronização em si (push/pull/init) ficam
em `routes/git.py` (`/api/workspace/git/*`) — aqui é só a conta GitHub.
"""

from __future__ import annotations

from fastapi import APIRouter, status

from nbplatform.api.deps import CurrentUser, SessionDep
from nbplatform.schemas.github import (
    GitHubAccountRead,
    GitHubBranchRead,
    GitHubConnectRequest,
    GitHubRepoRead,
)
from nbplatform.services.audit_service import AuditService
from nbplatform.services.github import account_service

router = APIRouter(prefix="/api/github", tags=["github"])


@router.get("/status", response_model=GitHubAccountRead)
async def github_status(session: SessionDep, user: CurrentUser) -> GitHubAccountRead:
    return await account_service.get_status(session, user.id)


@router.post("/auth", response_model=GitHubAccountRead)
async def github_connect(
    payload: GitHubConnectRequest, session: SessionDep, user: CurrentUser
) -> GitHubAccountRead:
    result = await account_service.connect(session, user.id, payload.token)
    await AuditService(session).record(
        user_id=user.id,
        action="GITHUB_CONNECT",
        resource_type="github_account",
        resource_id=str(user.id),
        metadata={"username": result.username or ""},
    )
    return result


@router.delete("/auth", status_code=status.HTTP_204_NO_CONTENT)
async def github_disconnect(session: SessionDep, user: CurrentUser) -> None:
    await account_service.disconnect(session, user.id)
    await AuditService(session).record(
        user_id=user.id,
        action="GITHUB_DISCONNECT",
        resource_type="github_account",
        resource_id=str(user.id),
    )


@router.get("/repos", response_model=list[GitHubRepoRead])
async def github_repos(session: SessionDep, user: CurrentUser) -> list[GitHubRepoRead]:
    return await account_service.list_repos(session, user.id)


@router.get("/repos/{owner}/{repo}/branches", response_model=list[GitHubBranchRead])
async def github_repo_branches(
    owner: str, repo: str, session: SessionDep, user: CurrentUser
) -> list[GitHubBranchRead]:
    return await account_service.list_branches(session, user.id, f"{owner}/{repo}")
