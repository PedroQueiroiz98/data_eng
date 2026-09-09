import { apiDelete, apiGet, apiPatch, apiPost, apiPut } from "@/lib/api";

export type AssistantProviderType = "OPENAI" | "AZURE_OPENAI" | "OLLAMA";

export const SECRET_MASK = "********";

export interface AssistantProvider {
  id: string;
  name: string;
  description: string | null;
  provider_type: AssistantProviderType;
  enabled: boolean;
  is_default: boolean;
  configuration: Record<string, unknown>;
  has_key: boolean;
  summary: string;
  created_at: string;
  updated_at: string;
}

export interface AssistantProviderInput {
  name: string;
  description: string | null;
  provider_type: AssistantProviderType;
  enabled: boolean;
  is_default: boolean;
  configuration: Record<string, unknown>;
  secret: string | null; // omit / "" / "********" = mantém
}

export interface AssistantTestResult {
  ok: boolean;
  detail: string;
  error: string | null;
}

export interface AiInteraction {
  id: string;
  task: string;
  provider_type: string | null;
  notebook_path: string | null;
  cell_id: string | null;
  model: string | null;
  prompt_chars: number;
  completion_chars: number;
  duration_ms: number | null;
  ok: boolean;
  error: string | null;
  result_text: string | null;
  title: string | null;
  created_at: string;
}

export interface AiInteractionPage {
  items: AiInteraction[];
  total: number;
  limit: number;
  offset: number;
}

export const listAssistantProviders = (): Promise<AssistantProvider[]> =>
  apiGet("/assistant/providers");

export const getAssistantProvider = (id: string): Promise<AssistantProvider> =>
  apiGet(`/assistant/providers/${id}`);

export const createAssistantProvider = (
  body: AssistantProviderInput,
): Promise<AssistantProvider> => apiPost("/assistant/providers", body);

export const updateAssistantProvider = (
  id: string,
  body: Partial<AssistantProviderInput>,
): Promise<AssistantProvider> => apiPut(`/assistant/providers/${id}`, body);

export const deleteAssistantProvider = (id: string): Promise<void> =>
  apiDelete(`/assistant/providers/${id}`);

export const setAssistantProviderEnabled = (
  id: string,
  enabled: boolean,
): Promise<AssistantProvider> =>
  apiPatch(`/assistant/providers/${id}/enabled`, { enabled });

export const testAssistantProvider = (id: string): Promise<AssistantTestResult> =>
  apiPost(`/assistant/providers/${id}/test`);

export const listAiInteractions = (
  params: { task?: string; notebook_path?: string; limit?: number } = {},
): Promise<AiInteractionPage> => {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== "") qs.set(k, String(v));
  }
  const s = qs.toString();
  return apiGet(`/assistant/interactions${s ? `?${s}` : ""}`);
};
