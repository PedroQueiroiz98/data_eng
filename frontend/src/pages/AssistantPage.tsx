import { useState } from "react";
import { useAuthContext } from "@/components/AuthProvider";
import {
  useAssistantProviders,
  useDeleteAssistantProvider,
  useTestAssistantProvider,
  useToggleAssistantProvider,
} from "@/hooks/useAssistantProviders";
import { useAiInteractions } from "@/hooks/useAssistant";
import type { AssistantProvider } from "@/lib/assistantProviders";
import { AiProviderDrawer } from "@/components/assistant/AiProviderDrawer";
import { AI_PROVIDER_META, AI_TASK_LABEL } from "@/components/assistant/providerMeta";
import { Button, Card, EmptyState, PageHeader, Switch, Tabs, useConfirm, useToast } from "@/ui";
import { AddIcon, ChatIcon, DeleteIcon, EditIcon, RunIcon } from "@/ui/icons";

export function AssistantPage() {
  const { user } = useAuthContext();
  const canManage = user?.role === "admin";
  const [tab, setTab] = useState("providers");

  return (
    <div>
      <PageHeader
        title="Assistente de IA"
        subtitle="Provedores de IA usados pelo editor de notebooks (geração, explicação, correção, inline)."
      />
      <div className="mb-4 flex gap-3 rounded-lg border border-surface-border bg-surface-variant/50 p-3 text-sm text-fg-muted">
        <ChatIcon className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
        <p>
          Configuração global (admin). A API key fica cifrada no servidor e nunca é
          retornada. O provedor marcado como padrão é o usado pelo editor.
        </p>
      </div>

      <Tabs
        tabs={[
          { id: "providers", label: "Provedores" },
          { id: "history", label: "Histórico" },
        ]}
        active={tab}
        onChange={setTab}
      />
      <div className="mt-4">
        {tab === "providers" ? <ProviderList canManage={canManage} /> : <History />}
      </div>
    </div>
  );
}

function ProviderList({ canManage }: { canManage: boolean }) {
  const { data, isLoading } = useAssistantProviders();
  const toast = useToast();
  const confirm = useConfirm();
  const del = useDeleteAssistantProvider();
  const toggle = useToggleAssistantProvider();
  const test = useTestAssistantProvider();
  const [drawer, setDrawer] = useState(false);
  const [editing, setEditing] = useState<AssistantProvider | null>(null);

  if (isLoading) return <p className="text-sm text-fg-faint">Carregando…</p>;

  return (
    <div className="space-y-3">
      {canManage && (
        <Button
          size="sm"
          icon={<AddIcon className="h-4 w-4" />}
          onClick={() => {
            setEditing(null);
            setDrawer(true);
          }}
        >
          Novo provedor
        </Button>
      )}
      {(data ?? []).length === 0 ? (
        <EmptyState
          icon={ChatIcon}
          title="Nenhum provedor de IA"
          description="Adicione um provedor OpenAI, Azure OpenAI ou Ollama para habilitar o assistente."
        />
      ) : (
        <div className="space-y-2">
          {(data ?? []).map((p) => {
            const meta = AI_PROVIDER_META[p.provider_type];
            return (
              <Card key={p.id} className="flex items-center gap-3">
                <meta.Icon className="h-5 w-5 shrink-0 text-fg-muted" />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 text-sm text-fg">
                    {p.name}
                    {p.is_default && (
                      <span className="rounded bg-primary-container/60 px-1.5 text-[11px] text-primary">
                        padrão
                      </span>
                    )}
                  </div>
                  <div className="text-xs text-fg-faint">
                    {meta.label} · {p.summary}
                    {p.has_key ? " · key ✓" : ""}
                  </div>
                </div>
                {canManage && (
                  <div className="flex items-center gap-1.5">
                    <Switch
                      checked={p.enabled}
                      onChange={(v) =>
                        toggle.mutate(
                          { id: p.id, enabled: v },
                          { onError: (e) => toast.error((e as Error).message) },
                        )
                      }
                      label=""
                    />
                    <button
                      type="button"
                      className="rounded p-1 text-fg-faint hover:bg-surface-variant"
                      title="Testar"
                      onClick={async () => {
                        const r = await test.mutateAsync(p.id).catch((e) => ({
                          ok: false,
                          error: (e as Error).message,
                          detail: "",
                        }));
                        r.ok ? toast.success(`OK: ${r.detail}`) : toast.error(r.error ?? "falhou");
                      }}
                    >
                      <RunIcon className="h-4 w-4" />
                    </button>
                    <button
                      type="button"
                      className="rounded p-1 text-fg-faint hover:bg-surface-variant"
                      onClick={() => {
                        setEditing(p);
                        setDrawer(true);
                      }}
                    >
                      <EditIcon className="h-4 w-4" />
                    </button>
                    <button
                      type="button"
                      className="rounded p-1 text-danger hover:bg-surface-variant"
                      onClick={async () => {
                        if (
                          await confirm({
                            title: `Excluir ${p.name}?`,
                            confirmLabel: "Excluir",
                            danger: true,
                          })
                        ) {
                          del.mutate(p.id, {
                            onError: (e) => toast.error((e as Error).message),
                          });
                        }
                      }}
                    >
                      <DeleteIcon className="h-4 w-4" />
                    </button>
                  </div>
                )}
              </Card>
            );
          })}
        </div>
      )}
      <AiProviderDrawer open={drawer} provider={editing} onClose={() => setDrawer(false)} />
    </div>
  );
}

function History() {
  const { data, isLoading } = useAiInteractions({ limit: 50 });
  if (isLoading) return <p className="text-sm text-fg-faint">Carregando…</p>;
  const items = data?.items ?? [];
  if (items.length === 0)
    return <p className="text-sm text-fg-faint">Nenhuma interação ainda.</p>;
  return (
    <div className="space-y-1.5 text-sm">
      {items.map((it) => (
        <details key={it.id} className="rounded border border-surface-border px-3 py-2">
          <summary className="cursor-pointer text-fg">
            <span className="text-fg-faint">
              {new Date(it.created_at).toLocaleString("pt-BR")} ·{" "}
            </span>
            {AI_TASK_LABEL[it.task] ?? it.task}
            {it.notebook_path ? ` · ${it.notebook_path}` : ""}
            {!it.ok && <span className="text-danger"> · falhou</span>}
          </summary>
          {it.result_text && (
            <pre className="mt-2 max-h-60 overflow-auto whitespace-pre-wrap font-mono text-xs text-fg-muted">
              {it.result_text}
            </pre>
          )}
          {it.error && <p className="mt-1 text-xs text-danger">{it.error}</p>}
        </details>
      ))}
    </div>
  );
}
