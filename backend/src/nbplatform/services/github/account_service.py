"""Conta do GitHub por usuário: conectar (valida PAT via API), status, repos,
branches, vínculo de repositório. O PAT cifrado (`SecretCipher`, mesma chave
dos providers de IA/notificação) nunca sai desta camada em texto claro.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nbplatform.core.config import get_settings
from nbplatform.core.crypto import SecretCipher
from nbplatform.core.errors import DomainValidationError
from nbplatform.models.github_account import UserGitHubAccount
from nbplatform.schemas.github import GitHubAccountRead, GitHubBranchRead, GitHubRepoRead
from nbplatform.services.github import client as gh_client


def _cipher() -> SecretCipher:
    return SecretCipher(get_settings().secret_encryption_key)


def _to_read(row: UserGitHubAccount) -> GitHubAccountRead:
    return GitHubAccountRead(
        connected=True,
        username=row.github_username,
        email=row.email,
        avatar_url=row.avatar_url,
        repo_full_name=row.repo_full_name,
        repo_default_branch=row.repo_default_branch,
        base_dir=row.base_dir,
        last_sync_at=row.last_sync_at,
    )


async def _get_account(session: AsyncSession, user_id: uuid.UUID) -> UserGitHubAccount | None:
    stmt = select(UserGitHubAccount).where(UserGitHubAccount.user_id == user_id)
    return await session.scalar(stmt)


async def get_status(session: AsyncSession, user_id: uuid.UUID) -> GitHubAccountRead:
    row = await _get_account(session, user_id)
    if row is None:
        return GitHubAccountRead(connected=False)
    return _to_read(row)


async def connect(session: AsyncSession, user_id: uuid.UUID, token: str) -> GitHubAccountRead:
    token = token.strip()
    if not token:
        raise DomainValidationError("Informe o Personal Access Token.")
    gh_user = await gh_client.get_authenticated_user(token)
    row = await _get_account(session, user_id)
    if row is None:
        row = UserGitHubAccount(
            user_id=user_id, token_ct="", github_user_id=gh_user.id, github_username=gh_user.login
        )
        session.add(row)
    row.token_ct = _cipher().encrypt(token)
    row.github_user_id = gh_user.id
    row.github_username = gh_user.login
    row.email = gh_user.email
    row.avatar_url = gh_user.avatar_url
    await session.flush()
    return _to_read(row)


async def disconnect(session: AsyncSession, user_id: uuid.UUID) -> None:
    row = await _get_account(session, user_id)
    if row is not None:
        await session.delete(row)
        await session.flush()


async def require_account_and_token(
    session: AsyncSession, user_id: uuid.UUID
) -> tuple[UserGitHubAccount, str]:
    """Usado pelas rotas de git remoto (`routes/git.py`): devolve o token
    decifrado só na memória da requisição — nunca persistido em claro/logado."""
    row = await _get_account(session, user_id)
    if row is None:
        raise DomainValidationError("Conecte sua conta do GitHub primeiro.")
    try:
        token = _cipher().decrypt(row.token_ct)
    except ValueError as exc:
        raise DomainValidationError(
            "Token do GitHub corrompido — desconecte e reconecte sua conta."
        ) from exc
    return row, token


async def list_repos(session: AsyncSession, user_id: uuid.UUID) -> list[GitHubRepoRead]:
    _, token = await require_account_and_token(session, user_id)
    repos = await gh_client.list_repos(token)
    return [
        GitHubRepoRead(
            full_name=r.full_name,
            private=r.private,
            default_branch=r.default_branch,
            clone_url=r.clone_url,
            updated_at=r.updated_at,
        )
        for r in repos
    ]


async def list_branches(
    session: AsyncSession, user_id: uuid.UUID, repo_full_name: str
) -> list[GitHubBranchRead]:
    _, token = await require_account_and_token(session, user_id)
    branches = await gh_client.list_branches(token, repo_full_name)
    return [GitHubBranchRead(name=b.name) for b in branches]


async def link_repo(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    repo_full_name: str,
    default_branch: str,
    base_dir: str,
) -> UserGitHubAccount:
    row, _ = await require_account_and_token(session, user_id)
    row.repo_full_name = repo_full_name
    row.repo_default_branch = default_branch
    row.base_dir = base_dir.strip().strip("/")
    await session.flush()
    return row


async def mark_synced(session: AsyncSession, user_id: uuid.UUID) -> None:
    row = await _get_account(session, user_id)
    if row is not None:
        row.last_sync_at = datetime.now(UTC)
        await session.flush()
