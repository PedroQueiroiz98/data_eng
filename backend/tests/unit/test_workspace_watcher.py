from __future__ import annotations

from pathlib import Path

from watchfiles import Change

from nbplatform.services.workspace_watcher import map_changes


def test_maps_add_modify_delete(tmp_path: Path) -> None:
    root = tmp_path
    (root / "a.py").write_text("x")
    raw = {
        (Change.added, str(root / "a.py")),
        (Change.modified, str(root / "b" / "c.csv")),
        (Change.deleted, str(root / "old.txt")),
    }
    out = {c["path"]: c["op"] for c in map_changes(root, raw)}
    assert out == {"a.py": "created", "b/c.csv": "updated", "old.txt": "deleted"}


def test_skips_internal_and_temp(tmp_path: Path) -> None:
    root = tmp_path
    raw = {
        (Change.modified, str(root / ".workspace" / "workspace.json")),
        (Change.added, str(root / ".git" / "HEAD")),
        (Change.added, str(root / "data" / ".gen-abc123")),
        (Change.added, str(root / "data" / ".write-xyz")),
        (Change.added, str(root / "keep.csv")),
    }
    out = [c["path"] for c in map_changes(root, raw)]
    assert out == ["keep.csv"]


def test_delete_wins_over_create_same_path(tmp_path: Path) -> None:
    root = tmp_path
    raw = {
        (Change.added, str(root / "x.txt")),
        (Change.deleted, str(root / "x.txt")),
    }
    out = map_changes(root, raw)
    assert len(out) == 1 and out[0]["op"] == "deleted"


def test_ignores_paths_outside_root(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    raw = {(Change.added, str(tmp_path / "elsewhere" / "y.txt"))}
    assert map_changes(root, raw) == []
