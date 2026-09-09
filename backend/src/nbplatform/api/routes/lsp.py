"""Endpoints do editor inteligente (autocomplete, hover, diagnósticos, ...).

Camada adicional: se cair, o editor e a execução via Papermill continuam. Todas
as rotas respondem 200 mesmo em falha do motor, com `ok=false`.
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path

from fastapi import APIRouter

from nbplatform.api.deps import CurrentUser, RedisDep
from nbplatform.core.config import get_settings
from nbplatform.schemas.lsp import (
    AutoImportRequest,
    AutoImportResponse,
    CompletionItemOut,
    CompletionRequest,
    CompletionResponse,
    DefinitionRequest,
    DiagnosticOut,
    DiagnosticsRequest,
    DiagnosticsResponse,
    HoverRequest,
    HoverResponse,
    ImportSuggestionOut,
    LocationOut,
    LocationsResponse,
    LspHealthResponse,
    ReferencesRequest,
    ResolveRequest,
    ResolveResponse,
    SignatureRequest,
    SignatureResponse,
)
from nbplatform.services.lsp import kernel_bridge
from nbplatform.services.lsp.jedi_backend import Completion
from nbplatform.services.lsp.service import LspResult, get_lsp_service

router = APIRouter(prefix="/api/lsp", tags=["lsp"])


def _ws_root(user: CurrentUser) -> str | None:
    """Raiz do projeto Jedi = a Home do usuário. Ignora qualquer `workspace_id`
    vindo do cliente (isolamento por usuário). Se a Home ainda não existe em
    disco, devolve None (Jedi trabalha só com o buffer)."""
    root = Path(get_settings().workspace_dir) / str(user.id)
    return str(root) if root.is_dir() else None


@router.get("/health", response_model=LspHealthResponse)
async def lsp_health() -> LspHealthResponse:
    return LspHealthResponse.model_validate(get_lsp_service().health())


_WORD_TAIL = re.compile(r"[A-Za-z_][A-Za-z0-9_]*$")


async def _kernel_completions(
    req: CompletionRequest, user: CurrentUser, redis: RedisDep
) -> kernel_bridge.KernelCompletion | None:
    """Completions do kernel vivo — só se a sessão for do usuário e estiver ociosa."""
    settings = get_settings()
    if not (req.session_id and settings.kernel_complete_enabled):
        return None
    if req.cell_index >= len(req.cells):
        return None
    try:
        meta = await redis.hgetall(settings.kernel_sess_key(req.session_id))
    except Exception:  # noqa: BLE001
        return None
    meta = {str(k): str(v) for k, v in (meta or {}).items()}
    if not meta or meta.get("user_id") != str(user.id) or meta.get("status") != "idle":
        return None
    code = req.cells[req.cell_index]
    cursor_pos = kernel_bridge.cursor_offset(code, req.line, req.column)
    try:
        return await asyncio.wait_for(
            kernel_bridge.request_completion(
                redis, req.session_id, code, cursor_pos, settings.kernel_complete_timeout_s
            ),
            timeout=settings.kernel_complete_timeout_s + 0.5,
        )
    except Exception:  # noqa: BLE001 - qualquer falha → só Jedi
        return None


@router.post("/completions", response_model=CompletionResponse)
async def completions(
    req: CompletionRequest, user: CurrentUser, redis: RedisDep
) -> CompletionResponse:
    # Caminho rápido do Jedi (sem projeto/CWD): completion não passa `_ws_root`.
    r = await get_lsp_service().complete(req.cells, req.cell_index, req.line, req.column)
    items: list[Completion] = list(r.completions)
    engine = r.engine
    if r.ok:
        kc = await _kernel_completions(req, user, redis)
        if kc:
            prefix_match = _WORD_TAIL.search(
                req.cells[req.cell_index][
                    : kernel_bridge.cursor_offset(
                        req.cells[req.cell_index], req.line, req.column
                    )
                ]
            )
            items = kernel_bridge.merge(
                items, kc, prefix_match.group(0) if prefix_match else ""
            )
            engine = "jedi+kernel"
    return CompletionResponse(
        ok=r.ok,
        engine=engine,
        took_ms=r.took_ms,
        items=[
            CompletionItemOut(
                label=c.label,
                insert_text=c.insert_text,
                kind=c.kind,
                detail=c.detail,
                documentation=c.documentation,
                call=c.call,
            )
            for c in items
        ],
    )


@router.post("/resolve", response_model=ResolveResponse)
async def resolve(req: ResolveRequest, user: CurrentUser) -> ResolveResponse:
    r = await get_lsp_service().resolve(
        req.cells, req.cell_index, req.line, req.column, req.label
    )
    item = r.completions[0] if r.completions else None
    return ResolveResponse(
        ok=r.ok,
        took_ms=r.took_ms,
        detail=item.detail if item else "",
        documentation=item.documentation if item else "",
        kind=item.kind if item else "",
    )


@router.post("/hover", response_model=HoverResponse)
async def hover(req: HoverRequest, user: CurrentUser) -> HoverResponse:
    r = await get_lsp_service().hover(req.cells, req.cell_index, req.line, req.column)
    if not r.hover:
        return HoverResponse(ok=r.ok, took_ms=r.took_ms)
    h = r.hover
    return HoverResponse(
        ok=True,
        took_ms=r.took_ms,
        name=h.name,
        kind=h.kind,
        full_name=h.full_name,
        signature=h.signature,
        documentation=h.documentation,
    )


@router.post("/signature", response_model=SignatureResponse)
async def signature(req: SignatureRequest, user: CurrentUser) -> SignatureResponse:
    r = await get_lsp_service().signature(req.cells, req.cell_index, req.line, req.column)
    if not r.signature:
        return SignatureResponse(ok=r.ok, took_ms=r.took_ms)
    s = r.signature
    return SignatureResponse(
        ok=True,
        took_ms=r.took_ms,
        label=s.label,
        parameters=s.parameters,
        active_parameter=s.active_parameter,
        documentation=s.documentation,
    )


@router.post("/definition", response_model=LocationsResponse)
async def definition(req: DefinitionRequest, user: CurrentUser) -> LocationsResponse:
    r = await get_lsp_service().definition(
        req.cells, req.cell_index, req.line, req.column, _ws_root(user)
    )
    return _locations(r)


@router.post("/references", response_model=LocationsResponse)
async def references(req: ReferencesRequest, user: CurrentUser) -> LocationsResponse:
    r = await get_lsp_service().references(
        req.cells, req.cell_index, req.line, req.column, _ws_root(user)
    )
    return _locations(r)


@router.post("/diagnostics", response_model=DiagnosticsResponse)
async def diagnostics(req: DiagnosticsRequest) -> DiagnosticsResponse:
    r = await get_lsp_service().diagnostics(req.cells)
    return DiagnosticsResponse(
        ok=r.ok,
        took_ms=r.took_ms,
        items=[DiagnosticOut.model_validate(d) for d in r.diagnostics],
    )


@router.post("/auto-import", response_model=AutoImportResponse)
async def auto_import(req: AutoImportRequest) -> AutoImportResponse:
    r = await get_lsp_service().auto_import(req.name)
    return AutoImportResponse(
        ok=r.ok,
        took_ms=r.took_ms,
        suggestions=[
            ImportSuggestionOut(label=s.label, statement=s.statement, module=s.module)
            for s in r.imports
        ],
    )


def _locations(r: LspResult) -> LocationsResponse:
    return LocationsResponse(
        ok=r.ok,
        took_ms=r.took_ms,
        locations=[
            LocationOut(
                cell_index=loc.cell_index,
                line=loc.line,
                column=loc.column,
                name=loc.name,
                external=loc.external,
                external_path=loc.external_path,
                module_name=loc.module_name,
                preview=loc.preview,
            )
            for loc in r.locations
        ],
    )
