"""Git local do Workspace: wrapper fino sobre o binário `git`.

Sem remoto/GitHub nesta rodada (init/status/diff/commit/branch/checkout/log/discard).
Lock por Workspace — nunca dois `git` concorrentes no mesmo diretório.
"""

from __future__ import annotations

import asyncio
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from nbplatform.core.config import get_settings
from nbplatform.core.errors import ConflictError, DomainValidationError

_locks: dict[str, asyncio.Lock] = {}
_REF_OK = re.compile(r"^[A-Za-z0-9._/\-]{1,200}$")


def _lock_for(key: str) -> asyncio.Lock:
    lock = _locks.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _locks[key] = lock
    return lock


def _validate_ref(name: str) -> None:
    if not _REF_OK.match(name) or ".." in name or name.startswith("-"):
        raise DomainValidationError(f"Nome de branch/ref inválido: {name!r}")


class GitError(ConflictError):
    """Falha numa operação git (HTTP 409)."""


@dataclass(slots=True)
class GitChange:
    path: str
    index: str
    worktree: str


@dataclass(slots=True)
class GitStatus:
    initialized: bool
    branch: str | None = None
    detached: bool = False
    ahead: int = 0
    behind: int = 0
    changes: list[GitChange] = field(default_factory=list)


@dataclass(slots=True)
class GitCommit:
    sha: str
    author: str
    date: str
    subject: str


class GitService:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.timeout = get_settings().git_op_timeout_s

    async def _run(
        self, *args: str, check: bool = True
    ) -> subprocess.CompletedProcess[str]:
        def _call() -> subprocess.CompletedProcess[str]:
            return subprocess.run(  # noqa: S603 - args controlados, sem shell
                ["git", *args],
                cwd=str(self.root),
                capture_output=True,
                text=True,
                timeout=self.timeout,
                env={
                    "GIT_TERMINAL_PROMPT": "0",
                    "GIT_CONFIG_NOSYSTEM": "1",
                    "HOME": str(self.root),
                    "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                },
            )

        try:
            proc = await asyncio.to_thread(_call)
        except subprocess.TimeoutExpired as exc:
            raise GitError(f"git {args[0]} excedeu o tempo limite") from exc
        if check and proc.returncode != 0:
            raise GitError((proc.stderr or proc.stdout or "git falhou").strip())
        return proc

    def _git_dir(self) -> Path:
        return self.root / ".git"

    async def is_initialized(self) -> bool:
        return await asyncio.to_thread(self._git_dir().exists)

    async def ensure_repo(self, *, author_name: str, author_email: str) -> None:
        async with _lock_for(str(self.root)):
            if self._git_dir().exists():
                return
            await self._run("init")
            await self._run("config", "user.name", author_name or "nbplatform")
            await self._run("config", "user.email", author_email or "nbplatform@local")
            await self._run("add", "-A")
            await self._run(
                "commit", "-m", "Commit inicial do Workspace", "--allow-empty"
            )

    async def status(self) -> GitStatus:
        if not await self.is_initialized():
            return GitStatus(initialized=False)
        proc = await self._run("status", "--porcelain=v2", "--branch", check=False)
        branch: str | None = None
        detached = False
        ahead = behind = 0
        changes: list[GitChange] = []
        for line in proc.stdout.splitlines():
            if line.startswith("# branch.head "):
                val = line.split(" ", 2)[2]
                if val == "(detached)":
                    detached = True
                else:
                    branch = val
            elif line.startswith("# branch.ab "):
                parts = line.split()
                ahead = int(parts[2].lstrip("+"))
                behind = int(parts[3].lstrip("-"))
            elif line.startswith(("1 ", "2 ")):
                fields = line.split(" ", 8)
                xy = fields[1]
                changes.append(
                    GitChange(path=fields[-1], index=xy[0], worktree=xy[1])
                )
            elif line.startswith("? "):
                changes.append(GitChange(path=line[2:], index="?", worktree="?"))
        return GitStatus(
            initialized=True,
            branch=branch,
            detached=detached,
            ahead=ahead,
            behind=behind,
            changes=changes,
        )

    async def diff(self, path: str | None) -> str:
        if not await self.is_initialized():
            return ""
        args = ["diff", "HEAD"]
        if path:
            args += ["--", path]
        proc = await self._run(*args, check=False)
        return proc.stdout

    async def log(self, limit: int) -> list[GitCommit]:
        if not await self.is_initialized():
            return []
        fmt = "%H%x1f%an%x1f%aI%x1f%s"
        proc = await self._run(
            "log", f"-{max(1, min(limit, 500))}", f"--pretty=format:{fmt}", check=False
        )
        out: list[GitCommit] = []
        for line in proc.stdout.splitlines():
            parts = line.split("\x1f")
            if len(parts) == 4:
                out.append(
                    GitCommit(sha=parts[0], author=parts[1], date=parts[2], subject=parts[3])
                )
        return out

    async def branches(self) -> list[str]:
        if not await self.is_initialized():
            return []
        proc = await self._run("branch", "--format=%(refname:short)", check=False)
        return [b.strip() for b in proc.stdout.splitlines() if b.strip()]

    async def create_branch(self, name: str) -> None:
        _validate_ref(name)
        async with _lock_for(str(self.root)):
            await self._run("checkout", "-b", name)

    async def checkout(self, ref: str) -> None:
        _validate_ref(ref)
        async with _lock_for(str(self.root)):
            await self._run("checkout", ref)

    async def commit(
        self,
        *,
        paths: list[str],
        message: str,
        author_name: str,
        author_email: str,
    ) -> str:
        if not message.strip():
            raise DomainValidationError("Mensagem de commit vazia.")
        async with _lock_for(str(self.root)):
            await self._run("config", "user.name", author_name or "nbplatform")
            await self._run("config", "user.email", author_email or "nbplatform@local")
            if paths:
                await self._run("add", "--", *paths)
            else:
                await self._run("add", "-A")
            proc = await self._run("commit", "-m", message, check=False)
            if proc.returncode != 0:
                raise GitError(
                    (proc.stderr or proc.stdout or "nada para commitar").strip()
                )
            head = await self._run("rev-parse", "HEAD")
            return head.stdout.strip()

    async def discard(self, paths: list[str]) -> None:
        async with _lock_for(str(self.root)):
            if paths:
                await self._run("checkout", "--", *paths, check=False)
                await self._run("clean", "-fd", "--", *paths, check=False)
            else:
                await self._run("checkout", "--", ".", check=False)
                await self._run("clean", "-fd", check=False)

    async def head_commit(self) -> str | None:
        if not await self.is_initialized():
            return None
        proc = await self._run("rev-parse", "HEAD", check=False)
        return proc.stdout.strip() or None
