import { TextField } from "@/ui";
import { SECRET_MASK, type AssistantProviderType } from "@/lib/assistantProviders";

export interface AiFormState {
  // comum
  model: string;
  temperature: string;
  inline: boolean;
  secret: string;
  // openai
  base_url: string;
  organization: string;
  // azure
  endpoint: string;
  deployment: string;
  api_version: string;
  // ollama
  ollama_base_url: string;
}

export const EMPTY_AI_FORM: AiFormState = {
  model: "",
  temperature: "0.2",
  inline: true,
  secret: "",
  base_url: "",
  organization: "",
  endpoint: "",
  deployment: "",
  api_version: "2024-06-01",
  ollama_base_url: "http://localhost:11434",
};

export function aiStateFromConfig(
  type: AssistantProviderType,
  cfg: Record<string, unknown>,
  hasKey: boolean,
): AiFormState {
  const c = cfg as Record<string, string | number | boolean | undefined>;
  return {
    ...EMPTY_AI_FORM,
    model: String(c.model ?? ""),
    temperature: c.temperature != null ? String(c.temperature) : "0.2",
    inline: c.inline == null ? true : Boolean(c.inline),
    secret: hasKey ? SECRET_MASK : "",
    base_url: String(c.base_url ?? ""),
    organization: String(c.organization ?? ""),
    endpoint: String(c.endpoint ?? ""),
    deployment: String(c.deployment ?? ""),
    api_version: String(c.api_version ?? "2024-06-01"),
    ollama_base_url: String(type === "OLLAMA" ? (c.base_url ?? "http://localhost:11434") : ""),
  };
}

export function aiConfigFromState(
  type: AssistantProviderType,
  s: AiFormState,
): { configuration: Record<string, unknown>; secret: string | null } {
  const temp = Number.parseFloat(s.temperature);
  const common = {
    temperature: Number.isFinite(temp) ? temp : 0.2,
    inline: s.inline,
  };
  if (type === "OPENAI") {
    return {
      configuration: {
        ...common,
        model: s.model.trim(),
        base_url: s.base_url.trim() || undefined,
        organization: s.organization.trim() || undefined,
      },
      secret: s.secret,
    };
  }
  if (type === "AZURE_OPENAI") {
    return {
      configuration: {
        ...common,
        endpoint: s.endpoint.trim(),
        deployment: s.deployment.trim(),
        api_version: s.api_version.trim() || "2024-06-01",
      },
      secret: s.secret,
    };
  }
  return {
    configuration: {
      ...common,
      model: s.model.trim(),
      base_url: s.ollama_base_url.trim() || "http://localhost:11434",
    },
    secret: s.secret || null,
  };
}

interface Props {
  type: AssistantProviderType;
  value: AiFormState;
  onChange: (patch: Partial<AiFormState>) => void;
}

export function AiProviderForm({ type, value, onChange }: Props) {
  return (
    <div className="space-y-3">
      {type === "OPENAI" && (
        <>
          <TextField
            label="Modelo *"
            placeholder="gpt-4o-mini"
            value={value.model}
            onChange={(e) => onChange({ model: e.target.value })}
          />
          <TextField
            label="Base URL"
            placeholder="https://api.openai.com/v1"
            value={value.base_url}
            onChange={(e) => onChange({ base_url: e.target.value })}
          />
          <TextField
            label="API Key *"
            type="password"
            value={value.secret}
            onChange={(e) => onChange({ secret: e.target.value })}
          />
          <TextField
            label="Organization"
            value={value.organization}
            onChange={(e) => onChange({ organization: e.target.value })}
          />
        </>
      )}

      {type === "AZURE_OPENAI" && (
        <>
          <TextField
            label="Endpoint *"
            placeholder="https://xxx.openai.azure.com"
            value={value.endpoint}
            onChange={(e) => onChange({ endpoint: e.target.value })}
          />
          <TextField
            label="Deployment *"
            value={value.deployment}
            onChange={(e) => onChange({ deployment: e.target.value })}
          />
          <TextField
            label="API version"
            value={value.api_version}
            onChange={(e) => onChange({ api_version: e.target.value })}
          />
          <TextField
            label="API Key *"
            type="password"
            value={value.secret}
            onChange={(e) => onChange({ secret: e.target.value })}
          />
        </>
      )}

      {type === "OLLAMA" && (
        <>
          <TextField
            label="Base URL *"
            placeholder="http://localhost:11434"
            value={value.ollama_base_url}
            onChange={(e) => onChange({ ollama_base_url: e.target.value })}
          />
          <TextField
            label="Modelo *"
            placeholder="llama3.1"
            value={value.model}
            onChange={(e) => onChange({ model: e.target.value })}
          />
        </>
      )}

      <div className="grid grid-cols-2 gap-3">
        <TextField
          label="Temperature"
          value={value.temperature}
          onChange={(e) => onChange({ temperature: e.target.value })}
        />
        <label className="flex items-end gap-2 pb-2 text-sm">
          <input
            type="checkbox"
            checked={value.inline}
            onChange={(e) => onChange({ inline: e.target.checked })}
          />
          Completions inline
        </label>
      </div>
      <p className="text-xs text-fg-faint">
        A API key nunca é retornada. Deixe em branco (ou <code>{SECRET_MASK}</code>) para
        manter a atual.
      </p>
    </div>
  );
}
