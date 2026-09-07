import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiDelete, apiGet, apiPut } from "@/lib/api";
import { useAuthContext } from "@/components/AuthProvider";

interface SecretMeta {
  key: string;
  created_at: string;
  updated_at: string;
}

const listSecrets = () => apiGet<SecretMeta[]>("/secrets");

export function Secrets() {
  const { user } = useAuthContext();
  const qc = useQueryClient();
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["secrets"],
    queryFn: listSecrets,
  });
  const save = useMutation({
    mutationFn: ({ key, value }: { key: string; value: string }) =>
      apiPut(`/secrets/${key}`, { value }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["secrets"] }),
  });
  const remove = useMutation({
    mutationFn: (key: string) => apiDelete(`/secrets/${key}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["secrets"] }),
  });

  const [key, setKey] = useState("");
  const [value, setValue] = useState("");

  if (user?.role !== "admin") {
    return (
      <div>
        <h1 className="text-2xl font-semibold">Secrets</h1>
        <p className="mt-2 text-slate-500">Acesso restrito a administradores.</p>
      </div>
    );
  }

  return (
    <div>
      <h1 className="text-2xl font-semibold">Secrets</h1>
      <p className="mt-1 text-sm text-slate-500">
        O valor é cifrado em repouso, injetado como env var na execução e mascarado nos logs.
        Nunca é retornado pela API.
      </p>

      <form
        onSubmit={async (e) => {
          e.preventDefault();
          if (!key.trim() || !value) return;
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
          type="password"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="valor"
          className="w-64 rounded border border-slate-300 px-2 py-1.5"
        />
        <button
          type="submit"
          disabled={save.isPending || !key.trim() || !value}
          className="rounded bg-slate-800 px-3 py-1.5 text-white disabled:opacity-40"
        >
          Salvar
        </button>
      </form>

      <section className="mt-6">
        {isLoading && <p className="text-slate-500">Carregando…</p>}
        {isError && <p className="text-red-600">{(error as Error).message}</p>}
        {data && data.length === 0 && <p className="text-slate-500">Nenhum secret.</p>}
        <ul className="divide-y divide-slate-100 rounded border border-slate-200">
          {data?.map((s) => (
            <li key={s.key} className="flex items-center justify-between px-4 py-2 text-sm">
              <span className="font-mono">{s.key}</span>
              <button
                type="button"
                onClick={() => {
                  if (confirm(`Excluir secret ${s.key}?`)) remove.mutate(s.key);
                }}
                className="text-xs text-red-600 hover:underline"
              >
                excluir
              </button>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
