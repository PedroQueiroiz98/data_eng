import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiDelete, apiGet, apiPut } from "@/lib/api";

interface Variable {
  key: string;
  value: string;
  scope: string;
  updated_at: string;
}

const listVariables = () => apiGet<Variable[]>("/variables");

export function Variables() {
  const qc = useQueryClient();
  const { data, isLoading, isError } = useQuery({
    queryKey: ["variables"],
    queryFn: listVariables,
  });
  const save = useMutation({
    mutationFn: ({ key, value }: { key: string; value: string }) =>
      apiPut(`/variables/${key}`, { value }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["variables"] }),
  });
  const remove = useMutation({
    mutationFn: (key: string) => apiDelete(`/variables/${key}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["variables"] }),
  });

  const [key, setKey] = useState("");
  const [value, setValue] = useState("");

  return (
    <div>
      <h1 className="text-2xl font-semibold">Variables</h1>
      <p className="mt-1 text-sm text-slate-500">
        Valores não-sensíveis, injetados como env var na execução. Podem ser sobrescritos ao
        rodar um Job (via parâmetros).
      </p>

      <form
        onSubmit={async (e) => {
          e.preventDefault();
          if (!key.trim()) return;
          await save.mutateAsync({ key: key.trim(), value });
          setKey("");
          setValue("");
        }}
        className="mt-4 flex gap-2 text-sm"
      >
        <input
          value={key}
          onChange={(e) => setKey(e.target.value)}
          placeholder="CHAVE"
          className="w-48 rounded border border-slate-300 px-2 py-1.5 font-mono"
        />
        <input
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="valor"
          className="w-64 rounded border border-slate-300 px-2 py-1.5"
        />
        <button
          type="submit"
          disabled={save.isPending || !key.trim()}
          className="rounded bg-slate-800 px-3 py-1.5 text-white disabled:opacity-40"
        >
          Salvar
        </button>
      </form>

      <section className="mt-6">
        {isLoading && <p className="text-slate-500">Carregando…</p>}
        {isError && <p className="text-red-600">Falha ao carregar variables.</p>}
        {data && data.length === 0 && <p className="text-slate-500">Nenhuma variável.</p>}
        <table className="w-full text-sm">
          <tbody>
            {data?.map((v) => (
              <tr key={`${v.scope}/${v.key}`} className="border-b border-slate-100">
                <td className="py-2 font-mono">{v.key}</td>
                <td className="py-2">{v.value}</td>
                <td className="py-2 text-xs text-slate-400">{v.scope}</td>
                <td className="py-2 text-right">
                  <button
                    type="button"
                    onClick={() => {
                      if (confirm(`Excluir variável ${v.key}?`)) remove.mutate(v.key);
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
      </section>
    </div>
  );
}
