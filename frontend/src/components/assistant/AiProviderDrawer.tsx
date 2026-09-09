import { useEffect, useMemo, useState } from "react";
import { Button, Drawer, Switch, Tabs, TextArea, TextField, useToast } from "@/ui";
import {
  useCreateAssistantProvider,
  useTestAssistantProvider,
  useUpdateAssistantProvider,
} from "@/hooks/useAssistantProviders";
import type {
  AssistantProvider,
  AssistantProviderInput,
  AssistantProviderType,
} from "@/lib/assistantProviders";
import { AI_PROVIDER_META } from "@/components/assistant/providerMeta";
import {
  AiProviderForm,
  aiConfigFromState,
  aiStateFromConfig,
  EMPTY_AI_FORM,
  type AiFormState,
} from "@/components/assistant/providerForms";

interface Props {
  open: boolean;
  onClose: () => void;
  provider: AssistantProvider | null;
}

const TYPES: AssistantProviderType[] = ["OPENAI", "AZURE_OPENAI", "OLLAMA"];

export function AiProviderDrawer({ open, onClose, provider }: Props) {
  const toast = useToast();
  const editing = !!provider;
  const create = useCreateAssistantProvider();
  const update = useUpdateAssistantProvider(provider?.id ?? "");
  const test = useTestAssistantProvider();

  const [tab, setTab] = useState("geral");
  const [type, setType] = useState<AssistantProviderType>("OPENAI");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [enabled, setEnabled] = useState(true);
  const [isDefault, setIsDefault] = useState(true);
  const [form, setForm] = useState<AiFormState>(EMPTY_AI_FORM);
  const [testResult, setTestResult] = useState<{ ok: boolean; msg: string } | null>(null);

  useEffect(() => {
    if (!open) return;
    setTab("geral");
    setTestResult(null);
    if (provider) {
      setType(provider.provider_type);
      setName(provider.name);
      setDescription(provider.description ?? "");
      setEnabled(provider.enabled);
      setIsDefault(provider.is_default);
      setForm(aiStateFromConfig(provider.provider_type, provider.configuration, provider.has_key));
    } else {
      setType("OPENAI");
      setName("");
      setDescription("");
      setEnabled(true);
      setIsDefault(true);
      setForm(EMPTY_AI_FORM);
    }
  }, [open, provider]);

  const body = useMemo((): AssistantProviderInput => {
    const cfg = aiConfigFromState(type, form);
    return {
      name: name.trim(),
      description: description.trim() || null,
      provider_type: type,
      enabled,
      is_default: isDefault,
      configuration: cfg.configuration,
      secret: cfg.secret,
    };
  }, [type, form, name, description, enabled, isDefault]);

  const submit = async () => {
    if (!name.trim()) {
      toast.error("Informe um nome.");
      setTab("geral");
      return;
    }
    try {
      if (editing) await update.mutateAsync(body);
      else await create.mutateAsync(body);
      toast.success(editing ? "Provedor atualizado" : "Provedor criado");
      onClose();
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  const runTest = async () => {
    if (!provider) return;
    setTestResult(null);
    try {
      const r = await test.mutateAsync(provider.id);
      setTestResult(
        r.ok
          ? { ok: true, msg: r.detail || "Conexão OK." }
          : { ok: false, msg: r.error || "Falha na conexão." },
      );
    } catch (e) {
      setTestResult({ ok: false, msg: (e as Error).message });
    }
  };

  const saving = create.isPending || update.isPending;

  return (
    <Drawer
      open={open}
      onClose={onClose}
      title={editing ? "Editar provedor de IA" : "Novo provedor de IA"}
      footer={
        <>
          <Button variant="text" onClick={onClose}>
            Cancelar
          </Button>
          <Button loading={saving} onClick={submit}>
            Salvar
          </Button>
        </>
      }
    >
      <Tabs
        tabs={[
          { id: "geral", label: "Geral" },
          { id: "config", label: "Configuração" },
          { id: "teste", label: "Teste" },
        ]}
        active={tab}
        onChange={setTab}
      />

      <div className="mt-4 space-y-4">
        {tab === "geral" && (
          <div className="space-y-4">
            <div>
              <span className="mb-1 block text-xs font-medium text-fg-muted">Tipo *</span>
              <div className="grid grid-cols-3 gap-2">
                {TYPES.map((t) => {
                  const meta = AI_PROVIDER_META[t];
                  const on = type === t;
                  return (
                    <button
                      key={t}
                      type="button"
                      disabled={editing}
                      onClick={() => setType(t)}
                      className={`rounded-lg border p-2 text-left text-xs transition ${
                        on
                          ? "border-primary bg-primary-container/40"
                          : "border-surface-border hover:bg-surface-variant"
                      } ${editing ? "opacity-60" : ""}`}
                    >
                      <span className="block font-medium text-fg">{meta.label}</span>
                      <span className="block text-[11px] text-fg-faint">{meta.hint}</span>
                    </button>
                  );
                })}
              </div>
            </div>
            <TextField label="Nome *" value={name} onChange={(e) => setName(e.target.value)} />
            <TextArea
              label="Descrição"
              rows={2}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
            <Switch checked={enabled} onChange={setEnabled} label="Ativo" />
            <Switch checked={isDefault} onChange={setIsDefault} label="Usar como padrão" />
          </div>
        )}

        {tab === "config" && (
          <AiProviderForm
            type={type}
            value={form}
            onChange={(p) => setForm((s) => ({ ...s, ...p }))}
          />
        )}

        {tab === "teste" && (
          <div className="space-y-3">
            {!editing ? (
              <p className="text-sm text-fg-faint">Salve o provedor para testá-lo.</p>
            ) : (
              <>
                <p className="text-sm text-fg-muted">
                  Envia um "ping" ao provedor com a configuração salva.
                </p>
                <Button variant="outlined" loading={test.isPending} onClick={runTest}>
                  {test.isPending ? "Testando…" : "Testar"}
                </Button>
                {testResult && (
                  <p className={`text-sm ${testResult.ok ? "text-ok" : "text-danger"}`}>
                    {testResult.ok ? "✓ " : "✕ "}
                    {testResult.msg}
                  </p>
                )}
              </>
            )}
          </div>
        )}
      </div>
    </Drawer>
  );
}
