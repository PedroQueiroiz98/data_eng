"""Schemas do editor inteligente (LSP-like sobre Jedi)."""

from __future__ import annotations

from pydantic import BaseModel, Field

MAX_CELLS = 500
MAX_CELL_CHARS = 100_000


class _PositionRequest(BaseModel):
    cells: list[str] = Field(min_length=1, max_length=MAX_CELLS)
    cell_index: int = Field(ge=0)
    line: int = Field(ge=0)
    column: int = Field(ge=0)


class CompletionRequest(_PositionRequest):
    pass


class HoverRequest(_PositionRequest):
    pass


class SignatureRequest(_PositionRequest):
    pass


class DefinitionRequest(_PositionRequest):
    pass


class ReferencesRequest(_PositionRequest):
    pass


class DiagnosticsRequest(BaseModel):
    cells: list[str] = Field(min_length=1, max_length=MAX_CELLS)


class AutoImportRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)


# ── respostas ────────────────────────────────────────────────────────────────
class CompletionItemOut(BaseModel):
    label: str
    insert_text: str
    kind: str
    detail: str = ""
    documentation: str = ""


class CompletionResponse(BaseModel):
    ok: bool
    engine: str = "jedi"
    took_ms: float = 0.0
    items: list[CompletionItemOut] = Field(default_factory=list)


class HoverResponse(BaseModel):
    ok: bool
    took_ms: float = 0.0
    name: str = ""
    kind: str = ""
    full_name: str = ""
    signature: str = ""
    documentation: str = ""


class SignatureResponse(BaseModel):
    ok: bool
    took_ms: float = 0.0
    label: str = ""
    parameters: list[str] = Field(default_factory=list)
    active_parameter: int = 0
    documentation: str = ""


class LocationOut(BaseModel):
    cell_index: int
    line: int
    column: int
    name: str
    external: bool
    external_path: str | None = None
    module_name: str = ""
    preview: str = ""


class LocationsResponse(BaseModel):
    ok: bool
    took_ms: float = 0.0
    locations: list[LocationOut] = Field(default_factory=list)


class DiagnosticOut(BaseModel):
    cell_index: int
    line: int
    column: int
    end_column: int | None = None
    severity: str
    message: str
    source: str
    code: str


class DiagnosticsResponse(BaseModel):
    ok: bool
    took_ms: float = 0.0
    items: list[DiagnosticOut] = Field(default_factory=list)


class ImportSuggestionOut(BaseModel):
    label: str
    statement: str
    module: str


class AutoImportResponse(BaseModel):
    ok: bool
    took_ms: float = 0.0
    suggestions: list[ImportSuggestionOut] = Field(default_factory=list)


class LspHealthResponse(BaseModel):
    enabled: bool
    ready: bool
    engine: str
    jedi_version: str
    python_version: str
    environment_path: str
