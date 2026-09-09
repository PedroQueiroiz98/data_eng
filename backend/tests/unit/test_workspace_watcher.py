from __future__ import annotations

from pathlib import Path

from watchfiles import Change

from nbplatform.services.workspace_watcher import map_changes

_UID_A = "00000000-0000-0000-0000-00000000000a"
_UID_B = "00000000-0000-0000-0000-00000000000b"


def test_groups_and_strips_owner_segment(tmp_path: Path) -> None:
    root = tmp_path
    raw = {
        (Change.added, str(root / _UID_A / "a.py")),
        (Change.modified, str(root / _UID_A / "sub" / "c.csv")),
        (Change.deleted, str(root / _UID_B / "old.txt")),
    }
    out = map_changes(root, raw)
    assert set(out) == {_UID_A, _UID_B}
    a = {c["path"]: c["op"] for c in out[_UID_A]}
    assert a == {"a.py": "created", "sub/c.csv": "updated"}
    assert out[_UID_B] == [{"op": "deleted", "path": "old.txt", "is_dir": False}]


def test_skips_internal_temp_and_rootlevel(tmp_path: Path) -> None:
    root = tmp_path
    raw = {
        (Change.modified, str(root / _UID_A / ".workspace" / "workspace.json")),
        (Change.added, str(root / _UID_A / ".git" / "HEAD")),
        (Change.added, str(root / _UID_A / "data" / ".gen-abc123")),
        (Change.added, str(root / "root-level-junk.txt")),  # sem segmento de usuário
        (Change.added, str(root / _UID_A / "keep.csv")),
    }
    out = map_changes(root, raw)
    assert list(out) == [_UID_A]
    assert [c["path"] for c in out[_UID_A]] == ["keep.csv"]


def test_delete_wins_over_create_same_path(tmp_path: Path) -> None:
    root = tmp_path
    raw = {
        (Change.added, str(root / _UID_A / "x.txt")),
        (Change.deleted, str(root / _UID_A / "x.txt")),
    }
    out = map_changes(root, raw)
    assert out[_UID_A] == [{"op": "deleted", "path": "x.txt", "is_dir": False}]


def test_ignores_paths_outside_root(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    raw = {(Change.added, str(tmp_path / "elsewhere" / _UID_A / "y.txt"))}
    assert map_changes(root, raw) == {}
