from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from nbplatform.core.errors import (
    ConflictError,
    DomainValidationError,
    ForbiddenError,
    NotFoundError,
)
from nbplatform.services.workspace_fs_service import WorkspaceFsService


def _svc(root: Path) -> WorkspaceFsService:
    root.mkdir(parents=True, exist_ok=True)
    for d in ("notebooks", "input", "output", ".workspace"):
        (root / d).mkdir(exist_ok=True)
    return WorkspaceFsService(
        root, max_upload_bytes=1024, max_nodes=1000, max_depth=12
    )


class _FakeUpload:
    def __init__(self, data: bytes, chunk: int = 3) -> None:
        self._buf = io.BytesIO(data)
        self._chunk = chunk

    async def read(self, size: int = -1) -> bytes:
        return self._buf.read(self._chunk if size < 0 else min(size, self._chunk))


async def test_write_and_read_text(tmp_path: Path) -> None:
    svc = _svc(tmp_path / "ws")
    await svc.write_file("scripts/util.py", text="x = 1\n", notebook=None)
    got = await svc.read_file("scripts/util.py")
    assert got.kind == "text"
    assert got.content == "x = 1\n"


async def test_write_notebook_validates(tmp_path: Path) -> None:
    svc = _svc(tmp_path / "ws")
    nb = {"nbformat": 4, "nbformat_minor": 5, "metadata": {}, "cells": []}
    res = await svc.write_file("notebooks/a.ipynb", text=None, notebook=nb)
    assert res.kind == "notebook"
    with pytest.raises(DomainValidationError):
        await svc.write_file("notebooks/bad.ipynb", text="not json", notebook=None)


async def test_tree_hides_internal_dir(tmp_path: Path) -> None:
    svc = _svc(tmp_path / "ws")
    await svc.write_file("notebooks/a.ipynb", text=None, notebook={
        "nbformat": 4, "nbformat_minor": 5, "metadata": {}, "cells": []})
    tree = await svc.list_tree()
    names = {c.name for c in (tree.children or [])}
    assert ".workspace" not in names
    assert "notebooks" in names


async def test_traversal_blocked(tmp_path: Path) -> None:
    svc = _svc(tmp_path / "ws")
    with pytest.raises(ForbiddenError):
        await svc.read_file("../../../etc/passwd")


async def test_rename_and_copy_and_delete(tmp_path: Path) -> None:
    svc = _svc(tmp_path / "ws")
    await svc.write_file("input/a.txt", text="hi", notebook=None)
    await svc.rename("input/a.txt", "input/b.txt")
    with pytest.raises(NotFoundError):
        await svc.read_file("input/a.txt")
    await svc.copy("input/b.txt", "output/b.txt")
    assert (await svc.read_file("output/b.txt")).content == "hi"
    with pytest.raises(ConflictError):
        await svc.copy("input/b.txt", "output/b.txt")
    await svc.delete("output/b.txt", recursive=False)


async def test_delete_non_empty_dir_requires_recursive(tmp_path: Path) -> None:
    svc = _svc(tmp_path / "ws")
    await svc.write_file("data/sub/x.txt", text="1", notebook=None)
    with pytest.raises(ConflictError):
        await svc.delete("data", recursive=False)
    await svc.delete("data", recursive=True)


async def test_upload_size_cap(tmp_path: Path) -> None:
    svc = _svc(tmp_path / "ws")
    await svc.save_upload("input", "small.bin", _FakeUpload(b"abc"))
    assert (svc.root / "input" / "small.bin").read_bytes() == b"abc"
    with pytest.raises(ConflictError):
        await svc.save_upload("input", "big.bin", _FakeUpload(b"x" * 5000))
    # arquivo temporário não deve ficar para trás
    assert not any(p.name.startswith(".upload-") for p in (svc.root / "input").iterdir())


async def test_download_file_and_dir_zip(tmp_path: Path) -> None:
    svc = _svc(tmp_path / "ws")
    await svc.write_file("output/r.txt", text="result", notebook=None)
    src, name, is_zip = await svc.open_download("output/r.txt")
    assert is_zip is False and isinstance(src, Path) and name == "r.txt"

    buf, zname, is_zip = await svc.open_download("output")
    assert is_zip is True and zname.endswith(".zip")
    with zipfile.ZipFile(buf) as zf:  # type: ignore[arg-type]
        assert "r.txt" in zf.namelist()
