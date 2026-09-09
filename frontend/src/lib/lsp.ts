/**
 * Cliente do editor inteligente (LSP-like sobre Jedi no backend).
 *
 * Camada adicional e resiliente: toda chamada tem timeout curto, nunca lança e
 * degrada para um resultado vazio. Se o backend cair, o editor continua 100%.
 */
import { getAuthToken } from "@/lib/api";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api";
const DEFAULT_TIMEOUT_MS = 4000;

// Timeouts por operação. As operações por-tecla (completion/hover/signature) são
// curtas de propósito: o servidor tem um timeout casado (`lsp_completion_timeout_s`),
// então um Jedi lento é abortado dos dois lados em vez de pendurar o editor.
export const TIMEOUTS = {
  complete: 3000,
  hover: 2500,
  signature: 2000,
  definition: 6000,
  references: 6000,
  diagnostics: 6000,
  resolve: 3000,
} as const;

export interface WorkspaceLspContext {
  /** dá ao Jedi ciência dos arquivos do Workspace (scripts/*.py) */
  workspaceId?: string;
  notebookPath?: string;
}

export interface Position extends WorkspaceLspContext {
  cells: string[];
  cellIndex: number;
  line: number; // 0-based
  column: number; // 0-based
  /** sessão de kernel ativa → completions cientes de objetos vivos */
  sessionId?: string;
}

export interface CompletionItem {
  label: string;
  insert_text: string;
  kind: string;
  detail: string;
  documentation: string;
  /** chamável (função/método/classe) — o editor acrescenta `(...)` */
  call?: boolean;
}
export interface CompletionResult {
  ok: boolean;
  engine: string;
  took_ms: number;
  items: CompletionItem[];
}

export interface ResolveResult {
  ok: boolean;
  detail: string;
  documentation: string;
  kind: string;
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

interface PostOpts {
  timeoutMs?: number;
  /** cancelamento externo (ex.: `token.onCancellationRequested` do Monaco) */
  signal?: AbortSignal;
}

async function post<T>(
  path: string,
  body: unknown,
  notOk: T,
  opts: PostOpts = {},
): Promise<T> {
  const timeoutMs = opts.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const ctrl = new AbortController();
  const onExternalAbort = () => ctrl.abort();
  if (opts.signal) {
    if (opts.signal.aborted) ctrl.abort();
    else opts.signal.addEventListener("abort", onExternalAbort, { once: true });
  }
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
    opts.signal?.removeEventListener("abort", onExternalAbort);
  }
}

const posBody = (p: Position) => ({
  cells: p.cells,
  cell_index: p.cellIndex,
  line: p.line,
  column: p.column,
  workspace_id: p.workspaceId,
  notebook_path: p.notebookPath,
  session_id: p.sessionId,
});

export const lspComplete = (p: Position, signal?: AbortSignal): Promise<CompletionResult> =>
  post(
    "/lsp/completions",
    posBody(p),
    { ok: false, engine: "jedi", took_ms: 0, items: [] },
    { timeoutMs: TIMEOUTS.complete, signal },
  );

export const lspResolve = (
  p: Position & { label: string },
  signal?: AbortSignal,
): Promise<ResolveResult> =>
  post(
    "/lsp/resolve",
    { ...posBody(p), label: p.label },
    { ok: false, detail: "", documentation: "", kind: "" },
    { timeoutMs: TIMEOUTS.resolve, signal },
  );

export const lspHover = (p: Position, signal?: AbortSignal): Promise<HoverResult> =>
  post(
    "/lsp/hover",
    posBody(p),
    { ok: false, name: "", kind: "", full_name: "", signature: "", documentation: "" },
    { timeoutMs: TIMEOUTS.hover, signal },
  );

export const lspSignature = (p: Position, signal?: AbortSignal): Promise<SignatureResult> =>
  post(
    "/lsp/signature",
    posBody(p),
    { ok: false, label: "", parameters: [], active_parameter: 0, documentation: "" },
    { timeoutMs: TIMEOUTS.signature, signal },
  );

export const lspDefinition = (p: Position, signal?: AbortSignal): Promise<LocationsResult> =>
  post("/lsp/definition", posBody(p), { ok: false, locations: [] }, {
    timeoutMs: TIMEOUTS.definition,
    signal,
  });

export const lspReferences = (p: Position, signal?: AbortSignal): Promise<LocationsResult> =>
  post("/lsp/references", posBody(p), { ok: false, locations: [] }, {
    timeoutMs: TIMEOUTS.references,
    signal,
  });

export const lspDiagnostics = (
  cells: string[],
  ctx?: WorkspaceLspContext,
): Promise<DiagnosticsResult> =>
  post(
    "/lsp/diagnostics",
    { cells, workspace_id: ctx?.workspaceId, notebook_path: ctx?.notebookPath },
    { ok: false, took_ms: 0, items: [] },
    { timeoutMs: TIMEOUTS.diagnostics },
  );

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
