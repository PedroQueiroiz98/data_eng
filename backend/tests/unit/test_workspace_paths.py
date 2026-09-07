from __future__ import annotations

import os
from pathlib import Path

import pytest

from nbplatform.core.errors import DomainValidationError, ForbiddenError
from nbplatform.domain.workspace_paths import (
    is_internal,
    is_ipynb,
    normalize_rel,
    rel_from_root,
    resolve_within,
)


@pytest.mark.parametrize(
    "rel",
    [
        "../etc/passwd",
        "a/../../b",
        "/abs/path",
        "notebooks/../../x",
        "..",
        "foo/../..",
    ],
)
def test_normalize_rel_rejects_traversal_and_absolute(rel: str) -> None:
    with pytest.raises(ForbiddenError):
        normalize_rel(rel)


@pytest.mark.parametrize("rel", ["", "   ", "a\x00b", "a\\b", "x" * 2000])
def test_normalize_rel_rejects_bad_input(rel: str) -> None:
    with pytest.raises(DomainValidationError):
        normalize_rel(rel)


def test_normalize_rel_collapses_dot_and_slashes() -> None:
    assert normalize_rel("./notebooks/./a.ipynb").as_posix() == "notebooks/a.ipynb"
    assert normalize_rel("input//clientes.csv").as_posix() == "input/clientes.csv"


def test_resolve_within_ok(tmp_path: Path) -> None:
    root = tmp_path / "ws"
    root.mkdir()
    resolved = resolve_within(root, "notebooks/extract.ipynb")
    assert resolved == (root / "notebooks" / "extract.ipynb").resolve()


def test_resolve_within_blocks_symlink_escape(tmp_path: Path) -> None:
    root = tmp_path / "ws"
    (root / "data").mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    link = root / "data" / "leak"
    try:
        os.symlink(outside, link)
    except (OSError, NotImplementedError):
        pytest.skip("symlink não suportado neste ambiente")
    with pytest.raises(ForbiddenError):
        resolve_within(root, "data/leak/secret.txt")


def test_rel_from_root(tmp_path: Path) -> None:
    root = tmp_path / "ws"
    (root / "output").mkdir(parents=True)
    p = root / "output" / "r.parquet"
    assert rel_from_root(root, p) == "output/r.parquet"


def test_is_internal_and_is_ipynb() -> None:
    assert is_internal(".workspace/workspace.json") is True
    assert is_internal("notebooks/x.ipynb") is False
    assert is_ipynb("a/b/c.IPYNB") is True
    assert is_ipynb("a/b/c.py") is False
