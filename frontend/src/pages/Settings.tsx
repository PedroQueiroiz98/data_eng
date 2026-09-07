import { useQuery } from "@tanstack/react-query";
import { useAuthContext } from "@/components/AuthProvider";
import { fetchReadiness, type Readiness } from "@/lib/api";
import { Card, PageHeader } from "@/ui";
import { LogsIcon } from "@/ui/icons";

export function Settings() {
  const { user } = useAuthContext();
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
    </div>
  );
}
