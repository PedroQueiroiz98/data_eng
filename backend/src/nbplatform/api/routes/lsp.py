"""Endpoints do editor inteligente (autocomplete, hover, diagnósticos, ...).

Camada adicional: se cair, o editor e a execução via Papermill continuam. Todas
as rotas respondem 200 mesmo em falha do motor, com `ok=false`.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from nbplatform.api.deps import CurrentUser
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
    SignatureRequest,
    SignatureResponse,
)
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


@router.post("/completions", response_model=CompletionResponse)
async def completions(req: CompletionRequest, user: CurrentUser) -> CompletionResponse:
    r = await get_lsp_service().complete(
        req.cells, req.cell_index, req.line, req.column, _ws_root(user)
    )
    return CompletionResponse(
        ok=r.ok,
        engine=r.engine,
        took_ms=r.took_ms,
        items=[
            CompletionItemOut(
                label=c.label,
                insert_text=c.insert_text,
                kind=c.kind,
                detail=c.detail,
                documentation=c.documentation,
            )
            for c in r.completions
        ],
    )


@router.post("/hover", response_model=HoverResponse)
async def hover(req: HoverRequest, user: CurrentUser) -> HoverResponse:
    r = await get_lsp_service().hover(
        req.cells, req.cell_index, req.line, req.column, _ws_root(user)
    )
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
    r = await get_lsp_service().signature(
        req.cells, req.cell_index, req.line, req.column, _ws_root(user)
    )
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
