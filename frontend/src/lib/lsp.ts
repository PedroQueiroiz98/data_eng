/**
 * Cliente do editor inteligente (LSP-like sobre Jedi no backend).
 *
 * Camada adicional e resiliente: toda chamada tem timeout curto, nunca lança e
 * degrada para um resultado vazio. Se o backend cair, o editor continua 100%.
 */
import { getAuthToken } from "@/lib/api";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api";
const DEFAULT_TIMEOUT_MS = 4000;

export interface Position {
  cells: string[];
  cellIndex: number;
  line: number; // 0-based
  column: number; // 0-based
}

export interface CompletionItem {
  label: string;
  insert_text: string;
  kind: string;
  detail: string;
  documentation: string;
}
export interface CompletionResult {
  ok: boolean;
  engine: string;
  took_ms: number;
  items: CompletionItem[];
}

export interface HoverResult {
  ok: boolean;
  name: string;
  kind: string;
  full_name: string;
  signature: string;
  documentation: string;
}

export interface SignatureResult {
  ok: boolean;
  label: string;
  parameters: string[];
  active_parameter: number;
  documentation: string;
}

export interface LspLocation {
  cell_index: number; // -1 => biblioteca externa
  line: number; // 0-based
  column: number;
  name: string;
  external: boolean;
  external_path: string | null;
  module_name: string;
  preview: string;
}
export interface LocationsResult {
  ok: boolean;
  locations: LspLocation[];
}

export interface LspDiagnostic {
  cell_index: number;
  line: number; // 0-based
  column: number;
  end_column: number | null;
  severity: "error" | "warning" | "information" | "hint";
  message: string;
  source: string;
  code: string;
}
export interface DiagnosticsResult {
  ok: boolean;
  took_ms: number;
  items: LspDiagnostic[];
}

export interface ImportSuggestion {
  label: string;
  statement: string;
  module: string;
}
export interface AutoImportResult {
  ok: boolean;
  suggestions: ImportSuggestion[];
}

export interface LspHealth {
  enabled: boolean;
  ready: boolean;
  engine: string;
  jedi_version: string;
  python_version: string;
  environment_path: string;
}

async function post<T>(path: string, body: unknown, notOk: T, timeoutMs = DEFAULT_TIMEOUT_MS): Promise<T> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const token = getAuthToken();
    const res = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      signal: ctrl.signal,
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(body),
    });
    if (!res.ok) return notOk;
    return (await res.json()) as T;
  } catch {
    return notOk;
  } finally {
    clearTimeout(timer);
  }
}

const posBody = (p: Position) => ({
  cells: p.cells,
  cell_index: p.cellIndex,
  line: p.line,
  column: p.column,
});

export const lspComplete = (p: Position): Promise<CompletionResult> =>
  post("/lsp/completions", posBody(p), { ok: false, engine: "jedi", took_ms: 0, items: [] });

export const lspHover = (p: Position): Promise<HoverResult> =>
  post("/lsp/hover", posBody(p), {
    ok: false,
    name: "",
    kind: "",
    full_name: "",
    signature: "",
    documentation: "",
  });

export const lspSignature = (p: Position): Promise<SignatureResult> =>
  post("/lsp/signature", posBody(p), {
    ok: false,
    label: "",
    parameters: [],
    active_parameter: 0,
    documentation: "",
  });

export const lspDefinition = (p: Position): Promise<LocationsResult> =>
  post("/lsp/definition", posBody(p), { ok: false, locations: [] });

export const lspReferences = (p: Position): Promise<LocationsResult> =>
  post("/lsp/references", posBody(p), { ok: false, locations: [] });

export const lspDiagnostics = (cells: string[]): Promise<DiagnosticsResult> =>
  post("/lsp/diagnostics", { cells }, { ok: false, took_ms: 0, items: [] }, 6000);

export const lspAutoImport = (name: string): Promise<AutoImportResult> =>
  post("/lsp/auto-import", { name }, { ok: false, suggestions: [] });

export async function lspHealth(): Promise<LspHealth> {
  const notOk: LspHealth = {
    enabled: false,
    ready: false,
    engine: "jedi",
    jedi_version: "",
    python_version: "",
    environment_path: "",
  };
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 3000);
  try {
    const token = getAuthToken();
    const res = await fetch(`${API_BASE}/lsp/health`, {
      signal: ctrl.signal,
      headers: { Accept: "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    });
    if (!res.ok) return notOk;
    return (await res.json()) as LspHealth;
  } catch {
    return notOk;
  } finally {
    clearTimeout(timer);
  }
}
