/**
 * Cliente do assistente de IA. Mesma filosofia do `lib/lsp.ts`: timeout curto,
 * nunca lança, degrada para um resultado vazio. Se a IA cair, o editor continua.
 */
import { getAuthToken } from "@/lib/api";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api";

export type AssistantTask =
  | "GENERATE"
  | "EXPLAIN"
  | "FIX"
  | "OPTIMIZE"
  | "TESTS"
  | "CONTINUE"
  | "CONVERT"
  | "DOCSTRING"
  | "CHAT"
  | "INLINE";

export interface AiErrorIn {
  ename: string;
  evalue: string;
  traceback: string[];
}

export interface AiContextIn {
  cells: string[];
  active_cell_index: number;
  cursor_line?: number | null;
  cursor_column?: number | null;
  selection?: string | null;
  recent_error?: AiErrorIn | null;
  notebook_path?: string | null;
  session_id?: string | null;
  workspace_files?: string[] | null;
}

export interface AiRunRequest {
  task: AssistantTask;
  context: AiContextIn;
  instruction?: string | null;
  messages?: { role: "system" | "user" | "assistant"; content: string }[] | null;
  target_language?: string | null;
  cell_id?: string | null;
}

export interface AiRunResult {
  ok: boolean;
  text: string;
  model: string;
  finish_reason: string;
  usage: Record<string, number>;
  error: string | null;
  interaction_id: string | null;
}

export interface AiAvailability {
  configured: boolean;
  provider_type: string | null;
  inline_enabled: boolean;
  models: string[];
}

function authHeaders(json = true): Record<string, string> {
  const token = getAuthToken();
  return {
    Accept: "application/json",
    ...(json ? { "Content-Type": "application/json" } : {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

const RUN_NOT_OK: AiRunResult = {
  ok: false,
  text: "",
  model: "",
  finish_reason: "",
  usage: {},
  error: "indisponível",
  interaction_id: null,
};

export async function assistantAvailability(): Promise<AiAvailability> {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), 4000);
  try {
    const res = await fetch(`${API_BASE}/assistant/availability`, {
      headers: authHeaders(false),
      signal: ctrl.signal,
    });
    if (!res.ok) throw new Error();
    return (await res.json()) as AiAvailability;
  } catch {
    return { configured: false, provider_type: null, inline_enabled: false, models: [] };
  } finally {
    clearTimeout(t);
  }
}

export async function assistantRun(
  body: AiRunRequest,
  signal?: AbortSignal,
): Promise<AiRunResult> {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), 60_000);
  signal?.addEventListener("abort", () => ctrl.abort(), { once: true });
  try {
    const res = await fetch(`${API_BASE}/assistant/run`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify(body),
      signal: ctrl.signal,
    });
    if (!res.ok) return RUN_NOT_OK;
    return (await res.json()) as AiRunResult;
  } catch {
    return RUN_NOT_OK;
  } finally {
    clearTimeout(t);
  }
}

export async function assistantInline(
  body: { context: AiContextIn },
  signal?: AbortSignal,
): Promise<string> {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), 3000);
  signal?.addEventListener("abort", () => ctrl.abort(), { once: true });
  try {
    const res = await fetch(`${API_BASE}/assistant/inline`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify(body),
      signal: ctrl.signal,
    });
    if (!res.ok) return "";
    const data = (await res.json()) as { ok: boolean; completion: string };
    return data.ok ? data.completion : "";
  } catch {
    return "";
  } finally {
    clearTimeout(t);
  }
}

export interface StreamHandlers {
  onDelta: (text: string) => void;
  onDone: (info: { error: string | null; interaction_id: string | null }) => void;
  signal?: AbortSignal;
}

/** Streaming SSE de `/assistant/run/stream`. Nunca lança. */
export async function assistantStream(
  body: AiRunRequest,
  { onDelta, onDone, signal }: StreamHandlers,
): Promise<void> {
  try {
    const res = await fetch(`${API_BASE}/assistant/run/stream`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify(body),
      signal,
    });
    if (!res.ok || !res.body) {
      onDone({ error: `HTTP ${res.status}`, interaction_id: null });
      return;
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";
    let done: { error: string | null; interaction_id: string | null } | null = null;
    for (;;) {
      const { value, done: streamDone } = await reader.read();
      if (streamDone) break;
      buf += decoder.decode(value, { stream: true });
      const parts = buf.split("\n\n");
      buf = parts.pop() ?? "";
      for (const part of parts) {
        const line = part.trim();
        if (!line.startsWith("data:")) continue;
        try {
          const frame = JSON.parse(line.slice(5).trim());
          if (frame.done) {
            done = {
              error: frame.error ?? null,
              interaction_id: frame.interaction_id ?? null,
            };
          } else if (typeof frame.delta === "string") {
            onDelta(frame.delta);
          }
        } catch {
          /* ignora frame malformado */
        }
      }
    }
    onDone(done ?? { error: null, interaction_id: null });
  } catch (e) {
    const aborted = (e as Error).name === "AbortError";
    onDone({ error: aborted ? null : "stream falhou", interaction_id: null });
  }
}
