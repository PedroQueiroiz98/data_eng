import { useEffect, useMemo, useState } from "react";
import {
  Button,
  Drawer,
  Switch,
  Tabs,
  TextArea,
  TextField,
  useToast,
} from "@/ui";
import {
  useCreateNotificationProvider,
  useTestNotificationProvider,
  useUpdateNotificationProvider,
} from "@/hooks/useNotificationProviders";
import type {
  NotificationProvider,
  NotificationProviderInput,
  NotificationProviderType,
} from "@/lib/notificationProviders";
import { PROVIDER_META } from "@/components/notifications/providerMeta";
import {
  BitrixProviderForm,
  bitrixConfigFromState,
  bitrixStateFromConfig,
  EMPTY_BITRIX,
  type BitrixFormState,
} from "@/components/notifications/BitrixProviderForm";
import {
  EmailProviderForm,
  emailConfigFromState,
  emailStateFromConfig,
  EMPTY_EMAIL,
  type EmailFormState,
} from "@/components/notifications/EmailProviderForm";

interface Props {
  open: boolean;
  onClose: () => void;
  provider: NotificationProvider | null; // null = criar
}

const TYPES: NotificationProviderType[] = ["BITRIX", "EMAIL"];

export function ProviderDrawer({ open, onClose, provider }: Props) {
  const toast = useToast();
  const editing = !!provider;
  const create = useCreateNotificationProvider();
  const update = useUpdateNotificationProvider(provider?.id ?? "");
  const test = useTestNotificationProvider();

  const [tab, setTab] = useState("geral");
  const [type, setType] = useState<NotificationProviderType>("BITRIX");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [enabled, setEnabled] = useState(true);
  const [email, setEmail] = useState<EmailFormState>(EMPTY_EMAIL);
  const [bitrix, setBitrix] = useState<BitrixFormState>(EMPTY_BITRIX);
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
      setEmail(emailStateFromConfig(provider.configuration, provider.has_password));
      setBitrix(bitrixStateFromConfig(provider.configuration, provider.has_credential));
    } else {
      setType("BITRIX");
      setName("");
      setDescription("");
      setEnabled(true);
      setEmail(EMPTY_EMAIL);
      setBitrix(EMPTY_BITRIX);
    }
  }, [open, provider]);

  const body = useMemo((): NotificationProviderInput => {
    const cfg =
      type === "EMAIL" ? emailConfigFromState(email) : bitrixConfigFromState(bitrix);
    return {
      name: name.trim(),
      description: description.trim() || null,
      provider_type: type,
      enabled,
      configuration: cfg.configuration,
      secret: cfg.secret,
    };
  }, [type, email, bitrix, name, description, enabled]);

  const submit = async () => {
    if (!name.trim()) {
      toast.error("Informe um nome.");
      setTab("geral");
      return;
    }
    try {
      if (editing) {
        await update.mutateAsync(body);
      } else {
        await create.mutateAsync(body);
      }
      toast.success(editing ? "Provider atualizado" : "Provider criado");
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
          ? { ok: true, msg: r.detail || "Notificação enviada com sucesso." }
          : { ok: false, msg: r.error || "Falha ao enviar notificação." },
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
      title={editing ? "Editar provedor de notificação" : "Novo provedor de notificação"}
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
              <span className="mb-1 block text-xs font-medium text-fg-muted">
                Tipo de provedor *
              </span>
              <div className="grid grid-cols-2 gap-2">
                {TYPES.map((t) => {
                  const meta = PROVIDER_META[t];
                  const on = type === t;
                  return (
                    <button
                      key={t}
                      type="button"
                      disabled={editing}
                      onClick={() => setType(t)}
                      className={`flex items-start gap-2 rounded-lg border p-3 text-left text-sm transition ${
                        on
                          ? "border-primary bg-primary-container/40"
                          : "border-surface-border hover:bg-surface-variant"
                      } ${editing ? "opacity-60" : ""}`}
                    >
                      <meta.Icon className="mt-0.5 h-5 w-5 shrink-0 text-fg-muted" />
                      <span>
                        <span className="block font-medium text-fg">{meta.label}</span>
                        <span className="block text-xs text-fg-faint">{meta.hint}</span>
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
            <TextField
              label="Nome *"
              value={name}
              placeholder="Bitrix Operações"
              onChange={(e) => setName(e.target.value)}
            />
            <TextArea
              label="Descrição"
              rows={2}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
            <div>
              <Switch checked={enabled} onChange={setEnabled} label="Ativo" />
              <p className="mt-1 text-xs text-fg-faint">
                Provedor disponível para envio de notificações.
              </p>
            </div>
          </div>
        )}

        {tab === "config" &&
          (type === "EMAIL" ? (
            <EmailProviderForm
              value={email}
              onChange={(p) => setEmail((s) => ({ ...s, ...p }))}
            />
          ) : (
            <BitrixProviderForm
              value={bitrix}
              onChange={(p) => setBitrix((s) => ({ ...s, ...p }))}
            />
          ))}

        {tab === "teste" && (
          <div className="space-y-3">
            {!editing ? (
              <p className="text-sm text-fg-faint">
                Salve o provedor para poder testá-lo.
              </p>
            ) : (
              <>
                <p className="text-sm text-fg-muted">
                  Envia uma notificação de teste usando a configuração salva. Nenhum
                  histórico é gerado.
                </p>
                <Button
                  variant="outlined"
                  loading={test.isPending}
                  onClick={runTest}
                >
                  {test.isPending ? "Testando…" : "Testar"}
                </Button>
                {testResult && (
                  <p
                    className={`text-sm ${
                      testResult.ok ? "text-ok" : "text-danger"
                    }`}
                  >
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
