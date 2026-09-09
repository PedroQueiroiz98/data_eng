"""Orquestra as operações do editor inteligente sobre o módulo virtual.

- stateless por request (recebe as células, monta o módulo virtual);
- roda o Jedi (síncrono) num pool de threads dedicado, com timeout por operação;
- mapeia posições de volta para (célula, linha, coluna);
- filtra identificadores sensíveis (password, token, ...);
- degradação graciosa: qualquer falha → resultado vazio + `ok=False`.
"""

from __future__ import annotations

import asyncio
import functools
import logging
import sys
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

from nbplatform.core.config import get_settings
from nbplatform.services.lsp import autoimport, jedi_backend
from nbplatform.services.lsp import diagnostics as diag_mod
from nbplatform.services.lsp.jedi_backend import (
    Completion,
    HoverInfo,
    Location,
    SignatureInfo,
)
from nbplatform.services.lsp.secret_names import is_sensitive_name
from nbplatform.services.lsp.virtual_module import VirtualModule

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CellLocation:
    cell_index: int  # -1 => definição externa (biblioteca)
    line: int  # 0-based na célula
    column: int
    name: str
    external: bool
    external_path: str | None
    module_name: str
    preview: str


@dataclass
class LspResult:
    ok: bool
    engine: str = "jedi"
    took_ms: float = 0.0
    completions: list[Completion] = field(default_factory=list)
    hover: HoverInfo | None = None
    signature: SignatureInfo | None = None
    locations: list[CellLocation] = field(default_factory=list)
    diagnostics: list[dict[str, object]] = field(default_factory=list)
    imports: list[autoimport.ImportSuggestion] = field(default_factory=list)


class LspService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._healthy = True
        # Pool dedicado: um `complete` patológico (Jedi não é cancelável) não
        # pode mais starvar o executor default compartilhado com o resto do app.
        self._pool = ThreadPoolExecutor(
            max_workers=max(1, self.settings.lsp_pool_workers),
            thread_name_prefix="jedi",
        )
        # Supersessão de completion: um `complete` mais novo torna o resultado
        # de um mais antivo obsoleto (evita "pilha" de sugestões atrasadas).
        self._complete_gen = 0
        if self.settings.lsp_enabled:
            jedi_backend.warmup()

    @property
    def env_path(self) -> str:
        return self.settings.lsp_environment_path or ""

    # ── util ────────────────────────────────────────────────────────────────
    def _prepare(self, cells: list[str]) -> VirtualModule | None:
        if not self.settings.lsp_enabled:
            return None
        vm = VirtualModule.build(cells)
        if len(vm.source) > self.settings.lsp_max_source_chars:
            return None
        return vm

    async def _run(
        self, fn: Callable[..., Any], *args: Any, timeout: float | None = None
    ) -> Any:
        loop = asyncio.get_running_loop()
        try:
            return await asyncio.wait_for(
                loop.run_in_executor(self._pool, fn, *args),
                timeout=timeout if timeout is not None else self.settings.lsp_timeout_s,
            )
        except Exception as exc:  # noqa: BLE001 - qualquer falha vira degradação graciosa
            self._healthy = False
            logger.warning("lsp op falhou (%s): %s", getattr(fn, "__name__", fn), exc)
            return None

    # ── operações ──────────────────────────────────────────────────────────
    async def complete(
        self,
        cells: list[str],
        cell_index: int,
        line: int,
        column: int,
        workspace_root: str | None = None,  # noqa: ARG002 - caminho rápido ignora
    ) -> LspResult:
        started = time.perf_counter()
        self._complete_gen += 1
        gen = self._complete_gen
        vm = self._prepare(cells)
        if vm is None:
            return LspResult(ok=False)
        try:
            abs_line, abs_col = vm.to_absolute(cell_index, line, column)
        except IndexError:
            return LspResult(ok=False)
        items: list[Completion] | None = await self._run(
            jedi_backend.complete,
            vm.source,
            abs_line,
            abs_col,
            self.env_path,
            self.settings.lsp_max_completions,
            self.settings.lsp_complete_signature_scan,
            timeout=self.settings.lsp_completion_timeout_s,
        )
        if gen != self._complete_gen:
            # superado por um request mais novo — descarta sem mexer em `_healthy`
            return LspResult(ok=False, took_ms=_ms(started))
        if items is None:
            return LspResult(ok=False, took_ms=_ms(started))
        self._healthy = True
        filtered = [c for c in items if not is_sensitive_name(c.label)]
        return LspResult(ok=True, completions=filtered, took_ms=_ms(started))

    async def resolve(
        self,
        cells: list[str],
        cell_index: int,
        line: int,
        column: int,
        label: str,
    ) -> LspResult:
        started = time.perf_counter()
        vm = self._prepare(cells)
        if vm is None:
            return LspResult(ok=False)
        try:
            abs_line, abs_col = vm.to_absolute(cell_index, line, column)
        except IndexError:
            return LspResult(ok=False)
        item: Completion | None = await self._run(
            jedi_backend.resolve,
            vm.source,
            abs_line,
            abs_col,
            label,
            self.env_path,
            timeout=self.settings.lsp_completion_timeout_s,
        )
        if item is None:
            return LspResult(ok=False, took_ms=_ms(started))
        self._healthy = True
        if is_sensitive_name(item.label):
            return LspResult(ok=True, took_ms=_ms(started))
        return LspResult(ok=True, completions=[item], took_ms=_ms(started))

    async def hover(
        self,
        cells: list[str],
        cell_index: int,
        line: int,
        column: int,
        workspace_root: str | None = None,  # noqa: ARG002 - caminho rápido ignora
    ) -> LspResult:
        started = time.perf_counter()
        vm = self._prepare(cells)
        if vm is None:
            return LspResult(ok=False)
        try:
            abs_line, abs_col = vm.to_absolute(cell_index, line, column)
        except IndexError:
            return LspResult(ok=False)
        info: HoverInfo | None = await self._run(
            jedi_backend.hover,
            vm.source,
            abs_line,
            abs_col,
            self.env_path,
            timeout=self.settings.lsp_completion_timeout_s,
        )
        if info is None:
            return LspResult(ok=False, took_ms=_ms(started))
        self._healthy = True
        if is_sensitive_name(info.name):
            return LspResult(ok=True, took_ms=_ms(started))
        return LspResult(ok=True, hover=info, took_ms=_ms(started))

    async def signature(
        self,
        cells: list[str],
        cell_index: int,
        line: int,
        column: int,
        workspace_root: str | None = None,  # noqa: ARG002 - caminho rápido ignora
    ) -> LspResult:
        started = time.perf_counter()
        vm = self._prepare(cells)
        if vm is None:
            return LspResult(ok=False)
        try:
            abs_line, abs_col = vm.to_absolute(cell_index, line, column)
        except IndexError:
            return LspResult(ok=False)
        info: SignatureInfo | None = await self._run(
            jedi_backend.signature,
            vm.source,
            abs_line,
            abs_col,
            self.env_path,
            timeout=self.settings.lsp_completion_timeout_s,
        )
        if info is None:
            return LspResult(ok=False, took_ms=_ms(started))
        self._healthy = True
        return LspResult(ok=True, signature=info, took_ms=_ms(started))

    async def definition(
        self,
        cells: list[str],
        cell_index: int,
        line: int,
        column: int,
        workspace_root: str | None = None,
    ) -> LspResult:
        return await self._locate(
            jedi_backend.goto, cells, cell_index, line, column, workspace_root
        )

    async def references(
        self,
        cells: list[str],
        cell_index: int,
        line: int,
        column: int,
        workspace_root: str | None = None,
    ) -> LspResult:
        return await self._locate(
            jedi_backend.references, cells, cell_index, line, column, workspace_root
        )

    async def _locate(
        self,
        fn: Callable[..., list[Location]],
        cells: list[str],
        cell_index: int,
        line: int,
        column: int,
        workspace_root: str | None = None,
    ) -> LspResult:
        started = time.perf_counter()
        vm = self._prepare(cells)
        if vm is None:
            return LspResult(ok=False)
        try:
            abs_line, abs_col = vm.to_absolute(cell_index, line, column)
        except IndexError:
            return LspResult(ok=False)
        raw: list[Location] | None = await self._run(
            fn, vm.source, abs_line, abs_col, self.env_path, workspace_root
        )
        if raw is None:
            return LspResult(ok=False, took_ms=_ms(started))
        self._healthy = True
        return LspResult(
            ok=True, locations=[_map_location(loc, vm) for loc in raw], took_ms=_ms(started)
        )

    async def diagnostics(self, cells: list[str]) -> LspResult:
        started = time.perf_counter()
        vm = self._prepare(cells)
        if vm is None:
            return LspResult(ok=False)
        raw: list[diag_mod.RawDiagnostic] | None = await self._run(diag_mod.analyze, vm.source)
        if raw is None:
            return LspResult(ok=False, took_ms=_ms(started))
        self._healthy = True
        out: list[dict[str, object]] = []
        for d in raw:
            ci, ln, col = vm.to_cell(d.line, d.column)
            out.append(
                {
                    "cell_index": ci,
                    "line": ln,
                    "column": col,
                    "end_column": d.end_column,
                    "severity": d.severity,
                    "message": d.message,
                    "source": d.source,
                    "code": d.code,
                }
            )
        return LspResult(ok=True, diagnostics=out, took_ms=_ms(started))

    async def auto_import(self, name: str) -> LspResult:
        started = time.perf_counter()
        if not self.settings.lsp_enabled:
            return LspResult(ok=False)
        res: list[autoimport.ImportSuggestion] | None = await self._run(
            autoimport.suggest, name, self.env_path
        )
        if res is None:
            return LspResult(ok=False, took_ms=_ms(started))
        self._healthy = True
        return LspResult(ok=True, imports=res, took_ms=_ms(started))

    def health(self) -> dict[str, object]:
        info = jedi_backend.runtime_info()
        return {
            "enabled": self.settings.lsp_enabled,
            "ready": self.settings.lsp_enabled and self._healthy,
            "engine": info["engine"],
            "jedi_version": info["jedi_version"],
            "python_version": info["python_version"],
            "environment_path": self.env_path or sys.executable,
        }


@functools.lru_cache(maxsize=1)
def get_lsp_service() -> LspService:
    """Singleton — mantém o sinal de saúde/circuit-breaker entre requests."""
    return LspService()


def _ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 1)


def _map_location(loc: Location, vm: VirtualModule) -> CellLocation:
    if loc.external:
        return CellLocation(
            cell_index=-1,
            line=max(0, loc.line - 1),
            column=loc.column,
            name=loc.name,
            external=True,
            external_path=loc.module_path,
            module_name=loc.module_name,
            preview=loc.code,
        )
    ci, ln, col = vm.to_cell(loc.line, loc.column)
    return CellLocation(
        cell_index=ci,
        line=ln,
        column=col,
        name=loc.name,
        external=False,
        external_path=None,
        module_name=loc.module_name,
        preview=loc.code,
    )
