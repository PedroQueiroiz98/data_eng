import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { CellCard } from "@/components/notebook/CellCard";
import { useExecuteNotebook } from "@/hooks/useExecutions";
import { useNotebook, useSaveVersion, useUpdateNotebook } from "@/hooks/useNotebooks";
import { useNotebookEditor } from "@/store/notebookEditor";

export function NotebookEditor() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const { data: notebook, isLoading, isError } = useNotebook(id);
  const save = useSaveVersion(id);
  const updateMeta = useUpdateNotebook(id);
  const execute = useExecuteNotebook(id);

  const { cells, dirty, load, addCell, toContent, markSaved } = useNotebookEditor();
  const [name, setName] = useState("");
  const [loadedVersion, setLoadedVersion] = useState<number | null>(null);
  const [showRun, setShowRun] = useState(false);
  const [paramsText, setParamsText] = useState("{}");
  const [paramsError, setParamsError] = useState<string | null>(null);

  useEffect(() => {
    if (notebook?.content && notebook.current_version !== loadedVersion) {
      load(notebook.content);
      setName(notebook.name);
      setLoadedVersion(notebook.current_version);
    }
  }, [notebook, loadedVersion, load]);

  if (isLoading) return <p className="text-slate-500">Carregando…</p>;
  if (isError || !notebook) return <p className="text-red-600">Notebook não encontrado.</p>;

  const onSave = async () => {
    if (name.trim() && name.trim() !== notebook.name) {
      await updateMeta.mutateAsync({ name: name.trim() });
    }
    await save.mutateAsync(toContent());
    markSaved();
    setLoadedVersion(null);
  };

  const onRun = async () => {
    let parameters: Record<string, unknown>;
    try {
      parameters = JSON.parse(paramsText || "{}") as Record<string, unknown>;
    } catch {
      setParamsError("JSON inválido");
      return;
    }
    if (dirty) await onSave();
    const exec = await execute.mutateAsync({ parameters });
    navigate(`/executions/${exec.id}`);
  };

  return (
    <div className="mx-auto max-w-4xl">
      <div className="mb-4 flex items-center gap-3">
        <Link to="/notebooks" className="text-sm text-slate-500 hover:underline">
          ← Notebooks
        </Link>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="flex-1 rounded border border-slate-300 px-2 py-1 text-lg font-medium"
        />
        <span className="text-xs text-slate-400">
          v{notebook.current_version} · {notebook.version_count} versões
        </span>
        {dirty && <span className="text-xs text-amber-600">• não salvo</span>}
        <button
          type="button"
          onClick={onSave}
          disabled={save.isPending || updateMeta.isPending}
          className="rounded border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50 disabled:opacity-40"
        >
          {save.isPending ? "Salvando…" : "Salvar versão"}
        </button>
        <button
          type="button"
          onClick={() => setShowRun((v) => !v)}
          className="rounded bg-slate-800 px-3 py-1.5 text-sm text-white"
        >
          Executar ▾
        </button>
      </div>

      {showRun && (
        <div className="mb-4 rounded border border-slate-200 bg-slate-50 p-3">
          <label className="mb-1 block text-xs font-medium text-slate-600">
            Parâmetros (JSON) — injetados via Papermill
          </label>
          <textarea
            value={paramsText}
            onChange={(e) => {
              setParamsText(e.target.value);
              setParamsError(null);
            }}
            rows={4}
            className="w-full rounded border border-slate-300 p-2 font-mono text-xs"
          />
          <div className="mt-2 flex items-center gap-2">
            <button
              type="button"
              onClick={onRun}
              disabled={execute.isPending}
              className="rounded bg-slate-800 px-3 py-1.5 text-sm text-white disabled:opacity-40"
            >
              {execute.isPending ? "Enfileirando…" : "Executar notebook"}
            </button>
            {paramsError && <span className="text-xs text-red-600">{paramsError}</span>}
            {execute.isError && (
              <span className="text-xs text-red-600">
                {(execute.error as Error).message}
              </span>
            )}
          </div>
        </div>
      )}

      {save.isError && (
        <p className="mb-3 text-sm text-red-600">
          Erro ao salvar: {(save.error as Error).message}
        </p>
      )}

      <div className="space-y-3">
        {cells.map((cell, i) => (
          <CellCard key={cell.localId} cell={cell} index={i} total={cells.length} />
        ))}
      </div>

      <div className="mt-4 flex gap-2">
        <button type="button" onClick={() => addCell("code", null)} className="btn-cell text-sm">
          + Código
        </button>
        <button type="button" onClick={() => addCell("markdown", null)} className="btn-cell text-sm">
          + Markdown
        </button>
      </div>
    </div>
  );
}
