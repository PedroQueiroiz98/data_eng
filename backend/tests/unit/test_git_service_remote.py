"""Remoto do GitService (fetch/push/pull/init_from_remote/abort_merge) contra
um bare repo local — sem rede, sem GitHub de verdade, sem Postgres/Redis. O
header de auth por-host (`http.https://github.com/.extraheader`) é um no-op
inofensivo pra um remoto `file://`, então o mesmo código de produção roda aqui.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from nbplatform.services.git_service import GitService

_TOKEN = "unused-token"  # remoto file:// não autentica; só exercita o code path


def _git(cwd: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=True,
        env={"GIT_CONFIG_NOSYSTEM": "1", "HOME": str(cwd)},
    )
    return proc.stdout


def _make_bare_remote(tmp_path: Path) -> Path:
    remote = tmp_path / "remote.git"
    remote.mkdir()
    _git(remote, "init", "--bare", "-b", "main")
    return remote


def _clone_seed(tmp_path: Path, remote: Path) -> Path:
    seed = tmp_path / "seed"
    _git(tmp_path, "clone", str(remote), str(seed))
    _git(seed, "config", "user.email", "seed@test")
    _git(seed, "config", "user.name", "seed")
    return seed


def _commit_and_push(seed: Path, filename: str, content: str, message: str) -> None:
    (seed / filename).write_text(content)
    _git(seed, "add", "-A")
    _git(seed, "commit", "-m", message)
    _git(seed, "push", "origin", "main")


async def test_init_from_remote_adopts_remote_when_local_is_fresh(tmp_path: Path) -> None:
    remote = _make_bare_remote(tmp_path)
    seed = _clone_seed(tmp_path, remote)
    _commit_and_push(seed, "readme.md", "hello from remote", "seed")

    local = tmp_path / "local"
    local.mkdir()
    svc = GitService(local)
    result = await svc.init_from_remote(
        _TOKEN,
        f"file://{remote}",
        "main",
        author_name="Tester",
        author_email="tester@test",
    )
    assert result.conflicts == []
    assert (local / "readme.md").read_text() == "hello from remote"
    st = await svc.status()
    assert st.branch == "main"
    assert st.remote_configured is True
    assert st.merging is False


async def test_push_then_another_clone_pulls_it(tmp_path: Path) -> None:
    remote = _make_bare_remote(tmp_path)
    seed = _clone_seed(tmp_path, remote)
    _commit_and_push(seed, "base.txt", "base", "seed")

    local = tmp_path / "local"
    local.mkdir()
    svc = GitService(local)
    await svc.init_from_remote(
        _TOKEN, f"file://{remote}", "main", author_name="Tester", author_email="tester@test"
    )
    (local / "new.txt").write_text("novo arquivo")
    await svc.commit(
        paths=[], message="add new.txt", author_name="Tester", author_email="tester@test"
    )
    await svc.push(_TOKEN, "main")

    other = tmp_path / "other-clone"
    other.mkdir()
    svc2 = GitService(other)
    result = await svc2.init_from_remote(
        _TOKEN, f"file://{remote}", "main", author_name="Tester2", author_email="tester2@test"
    )
    assert result.conflicts == []
    assert (other / "new.txt").read_text() == "novo arquivo"


async def test_pull_reports_conflicts_and_abort_merge_recovers(tmp_path: Path) -> None:
    remote = _make_bare_remote(tmp_path)
    seed = _clone_seed(tmp_path, remote)
    _commit_and_push(seed, "shared.txt", "linha original\n", "seed")

    local = tmp_path / "local"
    local.mkdir()
    svc = GitService(local)
    await svc.init_from_remote(
        _TOKEN, f"file://{remote}", "main", author_name="Tester", author_email="tester@test"
    )

    # divergência: alguém empurra uma mudança direto pro remoto...
    _commit_and_push(seed, "shared.txt", "mudança do remoto\n", "remote-change")

    # ...enquanto localmente o usuário edita a MESMA linha e comita
    (local / "shared.txt").write_text("mudança local\n")
    await svc.commit(
        paths=[], message="edita local", author_name="Tester", author_email="tester@test"
    )

    result = await svc.pull(_TOKEN, "main")
    assert result.conflicts == ["shared.txt"]

    st = await svc.status()
    assert st.merging is True
    assert any(c.path == "shared.txt" for c in st.changes)

    await svc.abort_merge()
    st2 = await svc.status()
    assert st2.merging is False
    assert (local / "shared.txt").read_text() == "mudança local\n"


async def test_pull_clean_fast_forward_no_conflicts(tmp_path: Path) -> None:
    remote = _make_bare_remote(tmp_path)
    seed = _clone_seed(tmp_path, remote)
    _commit_and_push(seed, "a.txt", "v1", "seed")

    local = tmp_path / "local"
    local.mkdir()
    svc = GitService(local)
    await svc.init_from_remote(
        _TOKEN, f"file://{remote}", "main", author_name="Tester", author_email="tester@test"
    )

    _commit_and_push(seed, "a.txt", "v2", "update")

    result = await svc.pull(_TOKEN, "main")
    assert result.conflicts == []
    assert (local / "a.txt").read_text() == "v2"
    st = await svc.status()
    assert st.merging is False
