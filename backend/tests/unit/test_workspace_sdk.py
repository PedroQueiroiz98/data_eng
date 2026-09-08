from __future__ import annotations

from pathlib import Path

import pytest

import workspace_sdk
from workspace_sdk._fs import WorkspaceSdkError


@pytest.fixture
def ws_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "wsroot"
    (root / "input").mkdir(parents=True)
    (root / "output").mkdir(parents=True)
    monkeypatch.setenv("WORKSPACE_ROOT", str(root))
    return root


def test_json_roundtrip(ws_root: Path) -> None:
    workspace_sdk.write_json({"ok": True, "n": 3}, "output/status.json")
    assert workspace_sdk.read_json("output/status.json") == {"ok": True, "n": 3}


def test_csv_roundtrip(ws_root: Path) -> None:
    rows = [{"a": "1", "b": "x"}, {"a": "2", "b": "y"}]
    workspace_sdk.write_csv(rows, "output/data.csv")
    # pandas é dependência agora → read_csv devolve DataFrame
    df = workspace_sdk.read_csv("output/data.csv")
    assert list(df.columns) == ["a", "b"]
    assert df.shape == (2, 2)
    assert df["b"].tolist() == ["x", "y"]
    assert df["a"].tolist() == [1, 2]


def test_list_and_exists(ws_root: Path) -> None:
    workspace_sdk.write_text("hi", "input/a.txt")
    assert workspace_sdk.exists("input/a.txt") is True
    assert "input/a.txt" in workspace_sdk.list("input")


def test_traversal_blocked(ws_root: Path) -> None:
    with pytest.raises(WorkspaceSdkError):
        workspace_sdk.read_text("../../../etc/passwd")


def test_requires_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("WORKSPACE_ROOT", raising=False)
    with pytest.raises(WorkspaceSdkError):
        workspace_sdk.read_text("x.txt")
