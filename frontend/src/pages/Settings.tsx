import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { useAuthContext } from "@/components/AuthProvider";
import { fetchReadiness, type Readiness } from "@/lib/api";
import { useEditorConfig } from "@/lib/editorConfig";
import { useAssistantAvailability } from "@/hooks/useAssistant";
import { Card, PageHeader, Switch } from "@/ui";
import { LogsIcon } from "@/ui/icons";

export function Settings() {
  const { user } = useAuthContext();
  const { config, setSection, reset } = useEditorConfig();
  const availability = useAssistantAvailability().data;
  const aiConfigured = !!availability?.configured;
  const { data } = useQuery<Readiness>({
    queryKey: ["readiness"],
    queryFn: fetchReadiness,
    refetchInterval: 10_000,
  });

  return (
    <div>
      <PageHeader title="Configuração" />

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-fg-faint">
            Sessão
          </h2>
          <div className="text-sm text-fg">{user?.name}</div>
          <div className="text-sm text-fg-muted">{user?.email}</div>
          <div className="mt-1 text-xs uppercase tracking-wide text-fg-faint">{user?.role}</div>
        </Card>

        <Card>
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-fg-faint">
            Observabilidade
          </h2>
          <a
            href="/metrics"
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1.5 text-sm text-primary hover:underline"
          >
            <LogsIcon className="h-4 w-4" />
            Métricas Prometheus (/metrics)
          </a>
        </Card>
      </div>

      <Card className="mt-4">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-fg-faint">
            Editor inteligente
          </h2>
          <button
            type="button"
            onClick={reset}
            className="text-xs text-primary hover:underline"
          >
            restaurar padrões
          </button>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <Switch
            checked={config.editor.autocomplete}
            onChange={(v) => setSection("editor", { autocomplete: v })}
            label="Autocomplete"
          />
          <Switch
            checked={config.editor.diagnostics}
            onChange={(v) => setSection("editor", { diagnostics: v })}
            label="Diagnósticos em tempo real"
          />
          <Switch
            checked={config.editor.signatureHelp}
            onChange={(v) => setSection("editor", { signatureHelp: v })}
            label="Ajuda de assinatura"
          />
          <Switch
            checked={config.editor.hover}
            onChange={(v) => setSection("editor", { hover: v })}
            label="Documentação ao passar o mouse"
          />
          <div>
            <Switch
              checked={config.editor.inlineSuggestions && aiConfigured}
              onChange={(v) => setSection("editor", { inlineSuggestions: v })}
              label="Sugestões inline (IA)"
            />
            {(!aiConfigured || !availability?.inline_enabled) && (
              <p className="mt-0.5 text-[11px] text-fg-faint">
                Configure um provedor em{" "}
                <Link to="/assistant" className="text-primary hover:underline">
                  /assistant
                </Link>
                .
              </p>
            )}
          </div>
          <div>
            <Switch
              checked={config.ai.enabled}
              onChange={(v) => setSection("ai", { enabled: v })}
              label="Assistente de IA no editor"
            />
            <p className="mt-0.5 text-[11px] text-fg-faint">
              {aiConfigured
                ? `Provedor: ${availability?.provider_type}`
                : "Nenhum provedor configurado."}{" "}
              <Link to="/assistant" className="text-primary hover:underline">
                gerenciar
              </Link>
            </p>
          </div>
        </div>
        <p className="mt-3 text-xs text-fg-faint">
          Language server: <span className="font-mono">{config.python.languageServer}</span>. Se o
          serviço cair, o editor e a execução via Papermill continuam funcionando.
        </p>
      </Card>

      <Card className="mt-4" padded={false}>
        <h2 className="border-b border-surface-border px-4 py-3 text-xs font-semibold uppercase tracking-wide text-fg-faint">
          Saúde dos serviços
        </h2>
        {data ? (
          <ul className="divide-y divide-surface-border text-sm">
            {Object.entries(data.checks).map(([name, c]) => (
              <li key={name} className="flex justify-between px-4 py-2.5">
                <span className="capitalize text-fg-muted">{name}</span>
                <span className={c.ok ? "text-ok" : "text-danger"}>
                  {c.ok ? "ok" : (c.detail ?? "indisponível")}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="px-4 py-6 text-sm text-fg-faint">Carregando…</p>
        )}
      </Card>

      <Card className="mt-4">
        <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-fg-faint">
          Notificações
        </h2>
        <p className="text-sm text-fg-muted">
          Os provedores de notificação (Email, Bitrix) são gerenciados na{" "}
          <Link to="/notifications" className="text-primary hover:underline">
            Central de Notificações
          </Link>
          .
        </p>
      </Card>

      <Card className="mt-4">
        <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-fg-faint">
          GitHub
        </h2>
        <p className="text-sm text-fg-muted">
          Conecte sua conta do GitHub e vincule um repositório ao seu Workspace na{" "}
          <Link to="/github" className="text-primary hover:underline">
            Integração GitHub
          </Link>
          .
        </p>
      </Card>
    </div>
  );
}
