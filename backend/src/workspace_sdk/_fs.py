"""Implementação do SDK. Stdlib apenas."""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path, PurePosixPath
from typing import IO, Any

_ENV_ROOT = "WORKSPACE_ROOT"


class WorkspaceSdkError(RuntimeError):
    pass


def _root() -> Path:
    raw = os.environ.get(_ENV_ROOT)
    if not raw:
        raise WorkspaceSdkError(
            f"${_ENV_ROOT} não definido — o SDK só funciona dentro de uma execução."
        )
    return Path(raw).resolve()


def _resolve(rel: str) -> Path:
    if not isinstance(rel, str) or not rel.strip():
        raise WorkspaceSdkError("Caminho vazio.")
    if "\x00" in rel or "\\" in rel:
        raise WorkspaceSdkError("Caminho inválido.")
    pure = PurePosixPath(rel.strip().lstrip("/"))
    if pure.is_absolute() or any(p == ".." for p in pure.parts):
        raise WorkspaceSdkError("Path traversal não permitido.")
    root = _root()
    target = (root / Path(*pure.parts)).resolve()
    if target != root and not target.is_relative_to(root):
        raise WorkspaceSdkError("Caminho fora do Workspace.")
    return target


class Workspace:
    """Fachada com métodos de conveniência sobre a raiz do Workspace."""

    @property
    def root(self) -> Path:
        return _root()

    def path(self, rel: str) -> Path:
        return _resolve(rel)

    def exists(self, rel: str) -> bool:
        return _resolve(rel).exists()

    def list(self, rel: str = "") -> list[str]:
        base = _root() if not rel else _resolve(rel)
        if not base.is_dir():
            raise WorkspaceSdkError(f"Não é um diretório: {rel or '/'}")
        return sorted(p.relative_to(_root()).as_posix() for p in base.iterdir())

    def open(self, rel: str, mode: str = "r", **kw: Any) -> IO[Any]:
        target = _resolve(rel)
        if any(c in mode for c in "wax"):
            target.parent.mkdir(parents=True, exist_ok=True)
        return open(target, mode, **kw)  # noqa: SIM115 - o chamador gerencia

    def read_text(self, rel: str, encoding: str = "utf-8") -> str:
        return _resolve(rel).read_text(encoding=encoding)

    def write_text(self, data: str, rel: str, encoding: str = "utf-8") -> Path:
        target = _resolve(rel)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(data, encoding=encoding)
        return target

    def read_json(self, rel: str) -> Any:
        return json.loads(self.read_text(rel))

    def write_json(self, obj: Any, rel: str, *, indent: int = 2) -> Path:
        return self.write_text(json.dumps(obj, ensure_ascii=False, indent=indent), rel)

    def read_csv(self, rel: str, **kw: Any) -> Any:
        try:
            import pandas as pd

            return pd.read_csv(_resolve(rel), **kw)
        except ModuleNotFoundError:
            with self.open(rel, "r", newline="", encoding="utf-8") as fh:
                return list(csv.DictReader(fh))

    def write_csv(self, data: Any, rel: str, **kw: Any) -> Path:
        target = _resolve(rel)
        target.parent.mkdir(parents=True, exist_ok=True)
        if hasattr(data, "to_csv"):  # DataFrame
            data.to_csv(target, index=kw.pop("index", False), **kw)
            return target
        rows = list(data)
        if not rows:
            target.write_text("", encoding="utf-8")
            return target
        with open(target, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        return target
