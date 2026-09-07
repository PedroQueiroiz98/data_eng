import { Link } from "react-router-dom";
import { StatusBadge } from "@/components/StatusBadge";
import { useExecutions } from "@/hooks/useExecutions";

function fmtDuration(ms: number | null): string {
  if (ms == null) return "—";
  const s = ms / 1000;
  if (s < 60) return `${s.toFixed(1)}s`;
  return `${Math.floor(s / 60)}m ${Math.round(s % 60)}s`;
}

export function Executions() {
  const { data, isLoading, isError } = useExecutions();

  return (
    <div>
      <h1 className="text-2xl font-semibold">Executions</h1>

      <section className="mt-5">
        {isLoading && <p className="text-slate-500">Carregando…</p>}
        {isError && <p className="text-red-600">Falha ao carregar execuções.</p>}
        {data && data.length === 0 && (
          <p className="text-slate-500">Nenhuma execução ainda. Rode um notebook.</p>
        )}

        {data && data.length > 0 && (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-slate-500">
                <th className="py-2 font-medium">Status</th>
                <th className="py-2 font-medium">Execução</th>
                <th className="py-2 font-medium">Tentativa</th>
                <th className="py-2 font-medium">Duração</th>
                <th className="py-2 font-medium">Criada</th>
              </tr>
            </thead>
            <tbody>
              {data.map((e) => (
                <tr key={e.id} className="border-b border-slate-100 hover:bg-slate-50">
                  <td className="py-2.5">
                    <StatusBadge status={e.status} />
                  </td>
                  <td className="py-2.5">
                    <Link to={`/executions/${e.id}`} className="font-mono text-xs text-blue-700 hover:underline">
                      {e.id.slice(0, 8)}
                    </Link>
                    {e.error_code && (
                      <span className="ml-2 text-xs text-red-600">{e.error_code}</span>
                    )}
                  </td>
                  <td className="py-2.5">#{e.attempt}</td>
                  <td className="py-2.5">{fmtDuration(e.duration_ms)}</td>
                  <td className="py-2.5 text-slate-500">
                    {new Date(e.created_at).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
