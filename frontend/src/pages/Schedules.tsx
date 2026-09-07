import { useState } from "react";
import {
  useCreateSchedule,
  useDeleteSchedule,
  useSchedules,
  useUpdateSchedule,
} from "@/hooks/useSchedules";
import { useWorkflows } from "@/hooks/useWorkflows";

export function Schedules() {
  const { data: schedules, isLoading, isError } = useSchedules();
  const { data: workflows } = useWorkflows();
  const create = useCreateSchedule();
  const toggle = useUpdateSchedule();
  const remove = useDeleteSchedule();

  const [workflowId, setWorkflowId] = useState("");
  const [cron, setCron] = useState("0 * * * *");
  const [timezone, setTimezone] = useState("UTC");
  const [error, setError] = useState<string | null>(null);

  const wfName = (id: string) => workflows?.find((w) => w.id === id)?.name ?? id.slice(0, 8);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!workflowId) return;
    try {
      await create.mutateAsync({ workflow_id: workflowId, cron, timezone });
      setWorkflowId("");
    } catch (err) {
      setError((err as Error).message);
    }
  };

  return (
    <div>
      <h1 className="text-2xl font-semibold">Schedules</h1>

      <form onSubmit={submit} className="mt-4 flex flex-wrap items-end gap-2 text-sm">
        <label>
          <span className="block text-xs text-slate-500">Workflow</span>
          <select
            value={workflowId}
            onChange={(e) => setWorkflowId(e.target.value)}
            className="rounded border border-slate-300 px-2 py-1"
          >
            <option value="">—</option>
            {workflows?.map((w) => (
              <option key={w.id} value={w.id}>
                {w.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span className="block text-xs text-slate-500">Cron</span>
          <input
            value={cron}
            onChange={(e) => setCron(e.target.value)}
            className="w-40 rounded border border-slate-300 px-2 py-1 font-mono"
          />
        </label>
        <label>
          <span className="block text-xs text-slate-500">Timezone</span>
          <input
            value={timezone}
            onChange={(e) => setTimezone(e.target.value)}
            className="w-40 rounded border border-slate-300 px-2 py-1"
          />
        </label>
        <button
          type="submit"
          disabled={create.isPending || !workflowId}
          className="rounded bg-slate-800 px-3 py-1.5 text-white disabled:opacity-40"
        >
          Agendar
        </button>
        {error && <span className="text-xs text-red-600">{error}</span>}
      </form>

      <section className="mt-6">
        {isLoading && <p className="text-slate-500">Carregando…</p>}
        {isError && <p className="text-red-600">Falha ao carregar schedules.</p>}
        {schedules && schedules.length === 0 && (
          <p className="text-slate-500">Nenhum schedule ainda.</p>
        )}

        {schedules && schedules.length > 0 && (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-slate-500">
                <th className="py-2 font-medium">Workflow</th>
                <th className="py-2 font-medium">Cron</th>
                <th className="py-2 font-medium">Próximo</th>
                <th className="py-2 font-medium">Ativo</th>
                <th className="py-2" />
              </tr>
            </thead>
            <tbody>
              {schedules.map((s) => (
                <tr key={s.id} className="border-b border-slate-100">
                  <td className="py-2.5">{wfName(s.workflow_id)}</td>
                  <td className="py-2.5 font-mono text-xs">
                    {s.cron} <span className="text-slate-400">{s.timezone}</span>
                  </td>
                  <td className="py-2.5 text-slate-500">
                    {s.next_run_at ? new Date(s.next_run_at).toLocaleString() : "—"}
                  </td>
                  <td className="py-2.5">
                    <button
                      type="button"
                      onClick={() => toggle.mutate({ id: s.id, enabled: !s.enabled })}
                      className={`rounded px-2 py-0.5 text-xs ${
                        s.enabled
                          ? "bg-green-100 text-green-700"
                          : "bg-slate-100 text-slate-500"
                      }`}
                    >
                      {s.enabled ? "ativo" : "inativo"}
                    </button>
                  </td>
                  <td className="py-2.5 text-right">
                    <button
                      type="button"
                      onClick={() => {
                        if (confirm("Excluir schedule?")) remove.mutate(s.id);
                      }}
                      className="text-xs text-red-600 hover:underline"
                    >
                      excluir
                    </button>
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
