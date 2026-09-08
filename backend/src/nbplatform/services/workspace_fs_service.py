"""Operações de arquivo dentro de um Workspace.

Toda I/O de disco é bloqueante → executada via `asyncio.to_thread`.
Todo caminho passa por `resolve_within` (domain/workspace_paths.py).
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import io
import json
import os
import shutil
import tempfile
import zipfile
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

from nbplatform.core.errors import ConflictError, DomainValidationError, NotFoundError
from nbplatform.domain.notebook_format import validate_notebook
from nbplatform.domain.workspace_paths import (
    INTERNAL_DIR,
    is_ipynb,
    normalize_rel,
    rel_from_root,
    resolve_within,
)

_TEXT_SNIFF_BYTES = 8192
_MAX_TEXT_BYTES = 5_000_000


@dataclass(slots=True)
class FileNode:
    name: str
    path: str  # relativo à raiz, POSIX
    type: Literal["file", "dir"]
    size: int | None = None
    modified_at: float | None = None
    children: list[FileNode] | None = None


@dataclass(slots=True)
class FileContent:
    path: str
    kind: Literal["notebook", "text", "binary"]
    content: dict[str, Any] | str | None  # json p/ notebook, str p/ texto, None p/ binário
    etag: str | None = None  # sha1 do conteúdo em disco (detecção de conflito no PUT)


@dataclass(slots=True)
class DataPreview:
    columns: list[str]
    dtypes: list[str]
    rows: list[list[Any]] = field(default_factory=list)
    total: int | None = None
    truncated: bool = False
    offset: int = 0


class WorkspaceFsService:
    def __init__(
        self,
        root: Path,
        *,
        max_upload_bytes: int,
        max_nodes: int,
        max_depth: int,
    ) -> None:
        self.root = root
        self.max_upload_bytes = max_upload_bytes
        self.max_nodes = max_nodes
        self.max_depth = max_depth

    # ── leitura ──────────────────────────────────────────────────────────────
    async def list_tree(self, *, rel_path: str = "", depth: int | None = None) -> FileNode:
        return await asyncio.to_thread(self._list_tree_sync, rel_path, depth)

    def _list_tree_sync(self, rel_path: str, depth: int | None) -> FileNode:
        base = self.root if not rel_path else resolve_within(self.root, rel_path)
        if not base.exists() or not base.is_dir():
            raise NotFoundError(f"Diretório não encontrado: {rel_path or '/'}")
        max_depth = self.max_depth if depth is None else min(depth, self.max_depth)
        counter = [0]

        def walk(d: Path, level: int) -> list[FileNode]:
            if level >= max_depth:
                return []
            out: list[FileNode] = []
            for entry in sorted(os.scandir(d), key=lambda e: (not e.is_dir(), e.name.lower())):
                if d == self.root and entry.name == INTERNAL_DIR:
                    continue
                counter[0] += 1
                if counter[0] > self.max_nodes:
                    raise ConflictError(
                        "Árvore do Workspace grande demais para listar de uma vez; "
                        "navegue por subpasta."
                    )
                node_path = rel_from_root(self.root, Path(entry.path))
                if entry.is_dir(follow_symlinks=False):
                    out.append(
                        FileNode(
                            name=entry.name,
                            path=node_path,
                            type="dir",
                            children=walk(Path(entry.path), level + 1),
                        )
                    )
                else:
                    st = entry.stat(follow_symlinks=False)
                    out.append(
                        FileNode(
                            name=entry.name,
                            path=node_path,
                            type="file",
                            size=st.st_size,
                            modified_at=st.st_mtime,
                        )
                    )
            return out

        return FileNode(
            name=base.name if rel_path else "",
            path=rel_path,
            type="dir",
            children=walk(base, 0),
        )

    async def read_file(self, rel_path: str) -> FileContent:
        return await asyncio.to_thread(self._read_file_sync, rel_path)

    def _read_file_sync(self, rel_path: str) -> FileContent:
        target = resolve_within(self.root, rel_path)
        if not target.exists() or not target.is_file():
            raise NotFoundError(f"Arquivo não encontrado: {rel_path}")
        rel = rel_from_root(self.root, target)
        raw = target.read_bytes()
        etag = hashlib.sha1(raw).hexdigest()
        if len(raw) > _MAX_TEXT_BYTES:
            return FileContent(path=rel, kind="binary", content=None, etag=etag)
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            return FileContent(path=rel, kind="binary", content=None, etag=etag)
        if b"\x00" in raw[:_TEXT_SNIFF_BYTES]:
            return FileContent(path=rel, kind="binary", content=None, etag=etag)
        if is_ipynb(rel):
            try:
                return FileContent(path=rel, kind="notebook", content=json.loads(text), etag=etag)
            except json.JSONDecodeError:
                return FileContent(path=rel, kind="text", content=text, etag=etag)
        return FileContent(path=rel, kind="text", content=text, etag=etag)

    # ── escrita ──────────────────────────────────────────────────────────────
    async def write_file(
        self,
        rel_path: str,
        *,
        text: str | None,
        notebook: dict[str, Any] | None,
        if_match: str | None = None,
    ) -> FileContent:
        return await asyncio.to_thread(self._write_file_sync, rel_path, text, notebook, if_match)

    def _write_file_sync(
        self,
        rel_path: str,
        text: str | None,
        notebook: dict[str, Any] | None,
        if_match: str | None = None,
    ) -> FileContent:
        target = resolve_within(self.root, rel_path)
        if target.is_dir():
            raise ConflictError(f"{rel_path} é um diretório.")
        if if_match is not None and target.is_file():
            current = hashlib.sha1(target.read_bytes()).hexdigest()
            if current != if_match:
                raise ConflictError(
                    "O arquivo mudou no disco desde a última leitura (edição concorrente "
                    "ou git). Recarregue antes de salvar."
                )
        if is_ipynb(rel_path):
            if notebook is None:
                if text is None:
                    raise DomainValidationError("Conteúdo do notebook ausente.")
                try:
                    notebook = json.loads(text)
                except json.JSONDecodeError as exc:
                    raise DomainValidationError(f"Notebook .ipynb inválido: {exc}") from exc
            validated = validate_notebook(notebook)
            payload = json.dumps(validated, ensure_ascii=False, indent=1)
        else:
            if text is None:
                raise DomainValidationError("Conteúdo de texto ausente.")
            payload = text
        target.parent.mkdir(parents=True, exist_ok=True)
        self._atomic_write_bytes(target, payload.encode("utf-8"))
        return self._read_file_sync(rel_from_root(self.root, target))

    async def make_dir(self, rel_path: str) -> FileNode:
        return await asyncio.to_thread(self._make_dir_sync, rel_path)

    def _make_dir_sync(self, rel_path: str) -> FileNode:
        target = resolve_within(self.root, rel_path)
        if target.exists() and target.is_file():
            raise ConflictError(f"{rel_path} já existe como arquivo.")
        target.mkdir(parents=True, exist_ok=True)
        return FileNode(name=target.name, path=rel_from_root(self.root, target), type="dir")

    async def delete(self, rel_path: str, *, recursive: bool) -> None:
        await asyncio.to_thread(self._delete_sync, rel_path, recursive)

    def _delete_sync(self, rel_path: str, recursive: bool) -> None:
        normalize_rel(rel_path)  # rejeita raiz / traversal
        target = resolve_within(self.root, rel_path)
        if target == self.root.resolve():
            raise ConflictError("Não é possível excluir a raiz do Workspace.")
        if not target.exists():
            raise NotFoundError(f"Caminho não encontrado: {rel_path}")
        if target.is_dir():
            if not recursive and any(target.iterdir()):
                raise ConflictError(f"Diretório {rel_path} não está vazio (use recursive=true).")
            shutil.rmtree(target)
        else:
            target.unlink()

    async def rename(self, src_rel: str, dst_rel: str) -> FileNode:
        return await asyncio.to_thread(self._rename_sync, src_rel, dst_rel)

    def _rename_sync(self, src_rel: str, dst_rel: str) -> FileNode:
        src = resolve_within(self.root, src_rel)
        dst = resolve_within(self.root, dst_rel)
        if not src.exists():
            raise NotFoundError(f"Origem não encontrada: {src_rel}")
        if dst.exists():
            raise ConflictError(f"Destino já existe: {dst_rel}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        return self._node_for(dst)

    async def copy(self, src_rel: str, dst_rel: str) -> FileNode:
        return await asyncio.to_thread(self._copy_sync, src_rel, dst_rel)

    def _copy_sync(self, src_rel: str, dst_rel: str) -> FileNode:
        src = resolve_within(self.root, src_rel)
        dst = resolve_within(self.root, dst_rel)
        if not src.exists():
            raise NotFoundError(f"Origem não encontrada: {src_rel}")
        if dst.exists():
            raise ConflictError(f"Destino já existe: {dst_rel}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)
        return self._node_for(dst)

    # ── upload / download ────────────────────────────────────────────────────
    async def save_upload(self, rel_dir: str, filename: str, source: Any) -> FileNode:
        """`source` é um objeto com `.read(size)` async (UploadFile do FastAPI)."""
        safe_name = Path(filename).name
        if not safe_name or safe_name in (".", ".."):
            raise DomainValidationError("Nome de arquivo inválido.")
        dst_rel = f"{rel_dir.rstrip('/')}/{safe_name}" if rel_dir else safe_name
        target = resolve_within(self.root, dst_rel)
        target.parent.mkdir(parents=True, exist_ok=True)

        tmp_fd, tmp_name = tempfile.mkstemp(dir=str(target.parent), prefix=".upload-")
        total = 0
        try:
            with os.fdopen(tmp_fd, "wb") as buf:
                while True:
                    chunk = await source.read(1024 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > self.max_upload_bytes:
                        raise ConflictError(
                            f"Upload excede o limite de {self.max_upload_bytes} bytes."
                        )
                    buf.write(chunk)
            await asyncio.to_thread(os.replace, tmp_name, target)
        except BaseException:
            await asyncio.to_thread(_silent_unlink, tmp_name)
            raise
        return await asyncio.to_thread(self._node_for, target)

    async def open_download(self, rel_path: str) -> tuple[Path | io.BytesIO, str, bool]:
        """Retorna (fonte, nome_sugerido, is_zip)."""
        return await asyncio.to_thread(self._open_download_sync, rel_path)

    def _open_download_sync(self, rel_path: str) -> tuple[Path | io.BytesIO, str, bool]:
        target = resolve_within(self.root, rel_path)
        if not target.exists():
            raise NotFoundError(f"Caminho não encontrado: {rel_path}")
        if target.is_file():
            return target, target.name, False
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for path in sorted(target.rglob("*")):
                if path.is_file():
                    zf.write(path, path.relative_to(target).as_posix())
        buf.seek(0)
        return buf, f"{target.name or 'workspace'}.zip", True

    # ── data viewer (.csv/.parquet) ─────────────────────────────────────────
    async def read_data(self, rel_path: str, *, offset: int, limit: int) -> DataPreview:
        return await asyncio.to_thread(self._read_data_sync, rel_path, offset, limit)

    def _read_data_sync(self, rel_path: str, offset: int, limit: int) -> DataPreview:
        target = resolve_within(self.root, rel_path)
        if not target.exists() or not target.is_file():
            raise NotFoundError(f"Arquivo não encontrado: {rel_path}")
        ext = target.suffix.lower()
        if ext == ".parquet":
            return _preview_parquet(target, offset, limit)
        if ext in (".csv", ".tsv"):
            return _preview_csv(target, offset, limit, delimiter="\t" if ext == ".tsv" else ",")
        raise DomainValidationError(f"Pré-visualização de dados não suportada para {ext}.")

    # ── export de notebook ──────────────────────────────────────────────────
    async def export_notebook(self, rel_path: str, fmt: str) -> tuple[bytes, str, str]:
        return await asyncio.to_thread(self._export_notebook_sync, rel_path, fmt)

    def _export_notebook_sync(self, rel_path: str, fmt: str) -> tuple[bytes, str, str]:
        target = resolve_within(self.root, rel_path)
        if not target.exists() or not target.is_file():
            raise NotFoundError(f"Arquivo não encontrado: {rel_path}")
        if not is_ipynb(rel_path):
            raise DomainValidationError("Exportação disponível apenas para .ipynb.")
        raw = target.read_bytes()
        stem = target.stem
        if fmt == "ipynb":
            return raw, f"{stem}.ipynb", "application/x-ipynb+json"
        if fmt == "py":
            import nbformat
            from nbconvert import PythonExporter

            nb = nbformat.reads(raw.decode("utf-8"), as_version=4)  # type: ignore[no-untyped-call]
            body, _ = PythonExporter().from_notebook_node(nb)  # type: ignore[no-untyped-call]
            return body.encode("utf-8"), f"{stem}.py", "text/x-python"
        raise DomainValidationError(f"Formato de exportação não suportado: {fmt}")

    # ── helpers ──────────────────────────────────────────────────────────────
    def _node_for(self, path: Path) -> FileNode:
        rel = rel_from_root(self.root, path)
        if path.is_dir():
            return FileNode(name=path.name, path=rel, type="dir")
        st = path.stat()
        return FileNode(
            name=path.name,
            path=rel,
            type="file",
            size=st.st_size,
            modified_at=st.st_mtime,
        )

    @staticmethod
    def _atomic_write_bytes(target: Path, data: bytes) -> None:
        tmp_fd, tmp_name = tempfile.mkstemp(dir=str(target.parent), prefix=".write-")
        try:
            with os.fdopen(tmp_fd, "wb") as buf:
                buf.write(data)
            os.replace(tmp_name, target)
        except BaseException:
            _silent_unlink(tmp_name)
            raise


def _silent_unlink(name: str) -> None:
    with contextlib.suppress(OSError):
        os.unlink(name)


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return str(value)


def _table_to_rows(table: Any) -> tuple[list[str], list[str], list[list[Any]]]:
    columns = [str(c) for c in table.column_names]
    dtypes = [str(t) for t in table.schema.types]
    pydict = table.to_pydict()
    n = table.num_rows
    rows = [[_json_safe(pydict[c][i]) for c in columns] for i in range(n)]
    return columns, dtypes, rows


def _preview_parquet(target: Path, offset: int, limit: int) -> DataPreview:
    import pyarrow.parquet as papq

    pf = papq.ParquetFile(str(target))
    total = int(pf.metadata.num_rows)
    collected: list[Any] = []
    seen = 0
    want_end = offset + limit
    for batch in pf.iter_batches(batch_size=max(1, min(limit, 1024))):
        rows_in_batch = batch.num_rows
        if seen + rows_in_batch <= offset:
            seen += rows_in_batch
            continue
        collected.append(batch)
        seen += rows_in_batch
        if seen >= want_end:
            break
    if not collected:
        schema = pf.schema_arrow
        return DataPreview(
            columns=[str(n) for n in schema.names],
            dtypes=[str(t) for t in schema.types],
            rows=[],
            total=total,
            offset=offset,
        )
    import pyarrow as pa

    table = pa.Table.from_batches(collected)
    local_offset = offset - (seen - table.num_rows)
    table = table.slice(max(0, local_offset), limit)
    columns, dtypes, rows = _table_to_rows(table)
    return DataPreview(
        columns=columns,
        dtypes=dtypes,
        rows=rows,
        total=total,
        truncated=offset + len(rows) < total,
        offset=offset,
    )


def _preview_csv(target: Path, offset: int, limit: int, *, delimiter: str) -> DataPreview:
    import pyarrow as pa
    import pyarrow.csv as pacsv

    reader = pacsv.open_csv(
        str(target),
        parse_options=pacsv.ParseOptions(delimiter=delimiter),
        read_options=pacsv.ReadOptions(block_size=1 << 20),
    )
    want_end = offset + limit
    collected: list[Any] = []
    seen = 0
    exhausted = False
    while seen < want_end:
        try:
            batch = reader.read_next_batch()
        except StopIteration:
            exhausted = True
            break
        if batch.num_rows == 0:
            exhausted = True
            break
        if seen + batch.num_rows <= offset:
            seen += batch.num_rows
            continue
        collected.append(batch)
        seen += batch.num_rows
    if not collected:
        schema = reader.schema
        return DataPreview(
            columns=[str(n) for n in schema.names],
            dtypes=[str(t) for t in schema.types],
            rows=[],
            total=seen if exhausted else None,
            offset=offset,
        )
    table = pa.Table.from_batches(collected)
    local_offset = offset - (seen - table.num_rows)
    table = table.slice(max(0, local_offset), limit)
    columns, dtypes, rows = _table_to_rows(table)
    # `total` só é conhecido se o stream se esgotou dentro da janela lida; caso
    # contrário fica None (o front mostra "N+ linhas" + "Carregar mais").
    total = seen if exhausted else None
    truncated = total is None or (offset + len(rows) < total)
    return DataPreview(
        columns=columns,
        dtypes=dtypes,
        rows=rows,
        total=total,
        truncated=truncated,
        offset=offset,
    )
