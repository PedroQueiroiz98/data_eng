import { useQuery } from "@tanstack/react-query";
import { fetchReadiness, type Readiness } from "@/lib/api";

const SERVICE_LABELS: Record<string, string> = {
  postgres: "PostgreSQL",
  redis: "Redis",
  worker: "Worker",
  scheduler: "Scheduler",
};

function StatusDot({ ok }: { ok: boolean }) {
  return (
    <span
      className={`inline-block h-2.5 w-2.5 rounded-full ${ok ? "bg-green-500" : "bg-red-500"}`}
      aria-hidden
    />
  );
}

export function Dashboard() {
  const { data, isLoading, isError, refetch, isFetching } = useQuery<Readiness>({
    queryKey: ["readiness"],
    queryFn: fetchReadiness,
    refetchInterval: 5_000,
  });

  return (
    <div>
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Dashboard</h1>
        <button
          type="button"
          onClick={() => void refetch()}
          className="rounded border border-slate-300 px-3 py-1 text-sm hover:bg-slate-50"
        >
          {isFetching ? "Atualizando…" : "Atualizar"}
        </button>
      </div>

      <section className="mt-6">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
          Saúde dos serviços
        </h2>

        {isLoading && <p className="text-slate-500">Carregando…</p>}
        {isError && <p className="text-red-600">Não foi possível consultar /ready.</p>}

        {data && (
          <>
            <p className="mb-3 text-sm">
              Estado geral:{" "}
              <span className={data.status === "ok" ? "text-green-700" : "text-red-700"}>
                {data.status === "ok" ? "operacional" : "degradado"}
              </span>
            </p>
            <ul className="divide-y divide-slate-100 rounded border border-slate-200">
              {Object.entries(data.checks).map(([name, check]) => (
                <li key={name} className="flex items-center justify-between px-4 py-3">
                  <span className="flex items-center gap-2">
                    <StatusDot ok={check.ok} />
                    {SERVICE_LABELS[name] ?? name}
                  </span>
                  <span className="text-sm text-slate-500">
                    {check.detail ?? (check.ok ? "ok" : "indisponível")}
                  </span>
                </li>
              ))}
            </ul>
          </>
        )}
      </section>
    </div>
  );
}
