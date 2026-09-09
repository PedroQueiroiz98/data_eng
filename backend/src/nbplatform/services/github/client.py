"""Cliente HTTP fino sobre a API REST do GitHub (`GET /user`, repos, branches).

Sem estado — recebe o PAT decifrado por chamada (nunca o guarda). Qualquer
falha de auth/rede vira `DomainValidationError` com mensagem amigável; quem
chama decide o que fazer (a rota devolve 422 direto pro front).
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from nbplatform.core.config import get_settings
from nbplatform.core.errors import DomainValidationError


@dataclass(slots=True, frozen=True)
class GitHubUser:
    id: int
    login: str
    name: str | None
    email: str | None
    avatar_url: str | None


@dataclass(slots=True, frozen=True)
class GitHubRepo:
    full_name: str
    private: bool
    default_branch: str
    clone_url: str
    updated_at: str


@dataclass(slots=True, frozen=True)
class GitHubBranch:
    name: str


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "nbplatform",
    }


def _make_client() -> httpx.AsyncClient:
    settings = get_settings()
    return httpx.AsyncClient(
        base_url=settings.github_api_base_url, timeout=settings.github_api_timeout_s
    )


async def _get(
    token: str, path: str, *, params: dict[str, str | int] | None = None
) -> httpx.Response:
    async with _make_client() as client:
        return await client.get(path, headers=_headers(token), params=params)


def _raise_for_status(resp: httpx.Response, *, action: str) -> None:
    if resp.status_code == 401:
        raise DomainValidationError("Token do GitHub inválido ou expirado.")
    if resp.status_code == 403:
        raise DomainValidationError(
            "GitHub recusou a requisição (rate limit ou permissão insuficiente — "
            "o token precisa do escopo `repo`)."
        )
    if resp.status_code == 404:
        raise DomainValidationError("Repositório não encontrado (ou sem acesso).")
    if resp.status_code >= 400:
        raise DomainValidationError(f"GitHub respondeu {resp.status_code} ao {action}.")


async def _primary_email(token: str) -> str | None:
    # `/user` só devolve e-mail se for público no perfil; `/user/emails` pede
    # o escopo `user:email` — best-effort, nunca falha a conexão por causa disso.
    resp = await _get(token, "/user/emails")
    if resp.status_code != 200:
        return None
    for entry in resp.json():
        if entry.get("primary"):
            return entry.get("email")
    return None


async def get_authenticated_user(token: str) -> GitHubUser:
    resp = await _get(token, "/user")
    _raise_for_status(resp, action="validar o token")
    data = resp.json()
    email = data.get("email") or await _primary_email(token)
    return GitHubUser(
        id=data["id"],
        login=data["login"],
        name=data.get("name"),
        email=email,
        avatar_url=data.get("avatar_url"),
    )


async def list_repos(token: str) -> list[GitHubRepo]:
    out: list[GitHubRepo] = []
    page = 1
    while page <= 5:  # até 500 repos — suficiente pra um PAT pessoal
        resp = await _get(
            token,
            "/user/repos",
            params={
                "per_page": 100,
                "page": page,
                "sort": "updated",
                "affiliation": "owner,collaborator",
            },
        )
        _raise_for_status(resp, action="listar repositórios")
        data = resp.json()
        if not data:
            break
        out.extend(
            GitHubRepo(
                full_name=r["full_name"],
                private=r["private"],
                default_branch=r.get("default_branch") or "main",
                clone_url=r["clone_url"],
                updated_at=r.get("updated_at") or "",
            )
            for r in data
        )
        if len(data) < 100:
            break
        page += 1
    return out


async def list_branches(token: str, repo_full_name: str) -> list[GitHubBranch]:
    resp = await _get(token, f"/repos/{repo_full_name}/branches", params={"per_page": 100})
    _raise_for_status(resp, action="listar branches")
    return [GitHubBranch(name=b["name"]) for b in resp.json()]
