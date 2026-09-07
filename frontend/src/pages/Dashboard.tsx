import { useMemo } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { fetchReadiness, type Readiness } from "@/lib/api";
import { useExecutions } from "@/hooks/useExecutions";
import { useSchedules } from "@/hooks/useSchedules";
import { useWorkflows } from "@/hooks/useWorkflows";
import { Card, PageHeader, StatCard, StatusChip } from "@/ui";
import { HistoryIcon, RefreshIcon, RunningIcon, ScheduleIcon } from "@/ui/icons";

function isToday(iso: string): boolean {
  const d = new Date(iso);
  const now = new Date();
  return (
    d.getFullYear() === now.getFullYear() &&
    d.getMonth() === now.getMonth() &&
    d.getDate() === now.getDate()
  );
}

function fmtDuration(ms: number | null): string {
  if (ms == null) return "—";
  const s = Math.round(ms / 1000);
  return s < 60 ? `${s}s` : `${Math.floor(s / 60)}m ${s % 60}s`;
}

export function Dashboard() {
  const { data: health, refetch, isFetching } = useQuery<Readiness>({
    queryKey: ["readiness"],
    queryFn: fetchReadiness,
    refetchInterval: 10_000,
  });
  const { data: executions } = useExecutions();
  const { data: schedules } = useSchedules();
  const { data: workflows } = useWorkflows();

  const stats = useMemo(() => {
    const xs = executions ?? [];
    return {
      today: xs.filter((e) => isToday(e.created_at)).length,
      success: xs.filter((e) => e.status === "SUCCESS").length,
      failed: xs.filter((e) => e.status === "FAILED" || e.status === "TIMEOUT").length,
      running: xs.filter((e) => e.status === "RUNNING").length,
    };
  }, [executions]);

  const recent = (executions ?? []).slice(0, 6);
  const wfName = (id: string) => workflows?.find((w) => w.id === id)?.name ?? id.slice(0, 8);
  const upcoming = (schedules ?? [])
    .filter((s) => s.enabled && s.next_run_at)
    .sort((a, b) => (a.next_run_at! < b.next_run_at! ? -1 : 1))
    .slice(0, 5);

  return (
    <div>
      <PageHeader
        title="Dashboard"
        actions={
          <button
            type="button"
            onClick={() => void refetch()}
            className="inline-flex items-center gap-1.5 rounded-md border border-surface-border bg-surface px-3 py-1.5 text-sm text-slate-600 hover:bg-surface-variant"
          >
            <RefreshIcon className={`h-4 w-4 ${isFetching ? "animate-spin" : ""}`} />
            Atualizar
          </button>
        }
      />

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard label="Execuções (hoje)" value={stats.today} icon={<HistoryIcon className="h-6 w-6" />} />
        <StatCard label="Sucesso" value={stats.success} tone="success" />
        <StatCard label="Falhas" value={stats.failed} tone="danger" />
        <StatCard
          label="Em execução"
          value={stats.running}
          tone="info"
          icon={<RunningIcon className={`h-6 w-6 ${stats.running ? "animate-spin" : ""}`} />}
        />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <section className="lg:col-span-2">
          <div className="mb-2 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-slate-700">Últimas execuções</h2>
            <Link to="/executions" className="text-xs text-primary hover:underline">
              ver todas
            </Link>
          </div>
          <Card padded={false}>
            {recent.length === 0 ? (
              <p className="px-4 py-6 text-sm text-slate-400">Nenhuma execução recente.</p>
            ) : (
              <ul className="divide-y divide-surface-border">
                {recent.map((e) => (
                  <li key={e.id}>
                    <Link
                      to={`/executions/${e.id}`}
                      className="flex items-center gap-3 px-4 py-2.5 text-sm hover:bg-surface-variant"
                    >
                      <StatusChip status={e.status} size="sm" />
                      <span className="font-mono text-xs text-slate-500">{e.id.slice(0, 8)}</span>
                      <span className="ml-auto text-xs text-slate-400">
                        {fmtDuration(e.duration_ms)} · {new Date(e.created_at).toLocaleTimeString()}
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </section>

        <section>
          <h2 className="mb-2 text-sm font-semibold text-slate-700">Próximos agendamentos</h2>
          <Card padded={false}>
            {upcoming.length === 0 ? (
              <p className="px-4 py-6 text-sm text-slate-400">Nenhum agendamento ativo.</p>
            ) : (
              <ul className="divide-y divide-surface-border">
                {upcoming.map((s) => (
                  <li key={s.id} className="flex items-center gap-2 px-4 py-2.5 text-sm">
                    <ScheduleIcon className="h-4 w-4 text-slate-400" />
                    <span className="truncate text-slate-700">{wfName(s.workflow_id)}</span>
                    <span className="ml-auto whitespace-nowrap text-xs text-slate-400">
                      {new Date(s.next_run_at!).toLocaleString()}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <h2 className="mb-2 mt-6 text-sm font-semibold text-slate-700">Serviços</h2>
          <Card padded={false}>
            <ul className="divide-y divide-surface-border text-sm">
              {health &&
                Object.entries(health.checks).map(([name, c]) => (
                  <li key={name} className="flex items-center justify-between px-4 py-2">
                    <span className="capitalize text-slate-600">{name}</span>
                    <span className={c.ok ? "text-green-600" : "text-red-600"}>
                      {c.ok ? "ok" : (c.detail ?? "indisponível")}
                    </span>
                  </li>
                ))}
            </ul>
          </Card>
        </section>
      </div>
    </div>
  );
}
