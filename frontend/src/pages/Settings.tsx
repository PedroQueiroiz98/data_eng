import { useQuery } from "@tanstack/react-query";
import { fetchReadiness, type Readiness } from "@/lib/api";
import { useAuthContext } from "@/components/AuthProvider";

export function Settings() {
  const { user } = useAuthContext();
  const { data } = useQuery<Readiness>({
    queryKey: ["readiness"],
    queryFn: fetchReadiness,
    refetchInterval: 10_000,
  });

  return (
    <div className="max-w-2xl">
      <h1 className="text-2xl font-semibold">Settings</h1>

      <section className="mt-5">
        <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
          Sessão
        </h2>
        <p className="text-sm text-slate-700">
          {user?.name} · {user?.email} · <span className="text-slate-400">{user?.role}</span>
        </p>
      </section>

      <section className="mt-6">
        <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
          Saúde
        </h2>
        {data ? (
          <ul className="divide-y divide-slate-100 rounded border border-slate-200 text-sm">
            {Object.entries(data.checks).map(([name, c]) => (
              <li key={name} className="flex justify-between px-4 py-2">
                <span>{name}</span>
                <span className={c.ok ? "text-green-600" : "text-red-600"}>
                  {c.ok ? "ok" : (c.detail ?? "indisponível")}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-slate-500">Carregando…</p>
        )}
      </section>

      <section className="mt-6">
        <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
          Observabilidade
        </h2>
        <p className="text-sm text-slate-600">
          Métricas Prometheus:{" "}
          <a href="/metrics" target="_blank" rel="noreferrer" className="text-blue-700 hover:underline">
            /metrics
          </a>
        </p>
      </section>
    </div>
  );
}
