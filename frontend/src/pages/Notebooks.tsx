import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useCreateNotebook, useDeleteNotebook, useNotebooks } from "@/hooks/useNotebooks";

export function Notebooks() {
  const navigate = useNavigate();
  const { data: notebooks, isLoading, isError } = useNotebooks();
  const create = useCreateNotebook();
  const remove = useDeleteNotebook();
  const [name, setName] = useState("");

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) return;
    const nb = await create.mutateAsync({ name: trimmed });
    setName("");
    navigate(`/notebooks/${nb.id}`);
  };

  return (
    <div>
      <h1 className="text-2xl font-semibold">Notebooks</h1>

      <form onSubmit={submit} className="mt-4 flex gap-2">
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Nome do novo notebook"
          className="w-72 rounded border border-slate-300 px-3 py-1.5 text-sm"
        />
        <button
          type="submit"
          disabled={create.isPending || !name.trim()}
          className="rounded bg-slate-800 px-3 py-1.5 text-sm text-white disabled:opacity-40"
        >
          {create.isPending ? "Criando…" : "Novo notebook"}
        </button>
      </form>

      <section className="mt-6">
        {isLoading && <p className="text-slate-500">Carregando…</p>}
        {isError && <p className="text-red-600">Falha ao carregar notebooks.</p>}

        {notebooks && notebooks.length === 0 && (
          <p className="text-slate-500">Nenhum notebook ainda.</p>
        )}

        {notebooks && notebooks.length > 0 && (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-slate-500">
                <th className="py-2 font-medium">Nome</th>
                <th className="py-2 font-medium">Versão</th>
                <th className="py-2 font-medium">Atualizado</th>
                <th className="py-2" />
              </tr>
            </thead>
            <tbody>
              {notebooks.map((nb) => (
                <tr
                  key={nb.id}
                  className="cursor-pointer border-b border-slate-100 hover:bg-slate-50"
                  onClick={() => navigate(`/notebooks/${nb.id}`)}
                >
                  <td className="py-2.5">
                    <div className="font-medium text-slate-800">{nb.name}</div>
                    {nb.description && (
                      <div className="text-xs text-slate-500">{nb.description}</div>
                    )}
                  </td>
                  <td className="py-2.5">v{nb.current_version}</td>
                  <td className="py-2.5 text-slate-500">
                    {new Date(nb.updated_at).toLocaleString()}
                  </td>
                  <td className="py-2.5 text-right">
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        if (confirm(`Excluir "${nb.name}"?`)) remove.mutate(nb.id);
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
