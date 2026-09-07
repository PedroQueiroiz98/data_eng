import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useCreateWorkflow, useDeleteWorkflow, useWorkflows } from "@/hooks/useWorkflows";

const STATUS_STYLE: Record<string, string> = {
  DRAFT: "bg-slate-100 text-slate-600",
  ACTIVE: "bg-green-100 text-green-700",
  DISABLED: "bg-amber-100 text-amber-800",
  ARCHIVED: "bg-slate-200 text-slate-500",
};

export function Workflows() {
  const navigate = useNavigate();
  const { data, isLoading, isError } = useWorkflows();
  const create = useCreateWorkflow();
  const remove = useDeleteWorkflow();
  const [name, setName] = useState("");

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) return;
    const wf = await create.mutateAsync({ name: trimmed });
    setName("");
    navigate(`/workflows/${wf.id}`);
  };

  return (
    <div>
      <h1 className="text-2xl font-semibold">Workflows</h1>

      <form onSubmit={submit} className="mt-4 flex gap-2">
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Nome do novo workflow"
          className="w-72 rounded border border-slate-300 px-3 py-1.5 text-sm"
        />
        <button
          type="submit"
          disabled={create.isPending || !name.trim()}
          className="rounded bg-slate-800 px-3 py-1.5 text-sm text-white disabled:opacity-40"
        >
          {create.isPending ? "Criando…" : "Novo workflow"}
        </button>
      </form>

      <section className="mt-6">
        {isLoading && <p className="text-slate-500">Carregando…</p>}
        {isError && <p className="text-red-600">Falha ao carregar workflows.</p>}
        {data && data.length === 0 && <p className="text-slate-500">Nenhum workflow ainda.</p>}

        {data && data.length > 0 && (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-slate-500">
                <th className="py-2 font-medium">Nome</th>
                <th className="py-2 font-medium">Status</th>
                <th className="py-2 font-medium">Atualizado</th>
                <th className="py-2" />
              </tr>
            </thead>
            <tbody>
              {data.map((wf) => (
                <tr
                  key={wf.id}
                  className="cursor-pointer border-b border-slate-100 hover:bg-slate-50"
                  onClick={() => navigate(`/workflows/${wf.id}`)}
                >
                  <td className="py-2.5 font-medium text-slate-800">{wf.name}</td>
                  <td className="py-2.5">
                    <span
                      className={`rounded px-2 py-0.5 text-xs ${STATUS_STYLE[wf.status] ?? ""}`}
                    >
                      {wf.status}
                    </span>
                  </td>
                  <td className="py-2.5 text-slate-500">
                    {new Date(wf.updated_at).toLocaleString()}
                  </td>
                  <td className="py-2.5 text-right">
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        if (confirm(`Excluir "${wf.name}"?`)) remove.mutate(wf.id);
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
