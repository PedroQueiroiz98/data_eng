import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { CellCard } from "@/components/notebook/CellCard";
import { useExecuteNotebook } from "@/hooks/useExecutions";
import { useNotebook, useSaveVersion, useUpdateNotebook } from "@/hooks/useNotebooks";
import { useNotebookEditor } from "@/store/notebookEditor";
import { Button, Dialog, PageHeader, TextArea, useToast } from "@/ui";
import { AddIcon, RunIcon, SaveIcon } from "@/ui/icons";

export function NotebookEditor() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
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

  if (isLoading) return <p className="text-sm text-slate-400">Carregando…</p>;
  if (isError || !notebook) return <p className="text-sm text-red-600">Notebook não encontrado.</p>;

  const onSave = async () => {
    if (name.trim() && name.trim() !== notebook.name) {
      await updateMeta.mutateAsync({ name: name.trim() });
    }
    await save.mutateAsync(toContent());
    markSaved();
    setLoadedVersion(null);
    toast.success("Notebook salvo");
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
    toast.success("Execução iniciada");
    setShowRun(false);
    navigate(`/executions/${exec.id}`);
  };

  return (
    <div>
      <PageHeader
        back={{ to: "/notebooks", label: "Notebooks" }}
        title={
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full max-w-md rounded-md border border-transparent bg-transparent px-1 py-0.5 text-2xl font-semibold hover:border-surface-border focus:border-primary focus:bg-surface focus:outline-none"
          />
        }
        subtitle={
          <span className="flex items-center gap-2 text-xs">
            <span>
              v{notebook.current_version} · {notebook.version_count} versões
            </span>
            {dirty && (
              <span className="rounded-full bg-amber-100 px-2 py-0.5 font-medium text-amber-700">
                alterações não salvas
              </span>
            )}
          </span>
        }
        actions={
          <>
            <Button
              variant="outlined"
              size="sm"
              icon={<SaveIcon className="h-4 w-4" />}
              loading={save.isPending || updateMeta.isPending}
              onClick={onSave}
            >
              Salvar
            </Button>
            <Button size="sm" icon={<RunIcon className="h-4 w-4" />} onClick={() => setShowRun(true)}>
              Executar
            </Button>
          </>
        }
      />

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
        <Button
          variant="tonal"
          size="sm"
          icon={<AddIcon className="h-4 w-4" />}
          onClick={() => addCell("code", null)}
        >
          Código
        </Button>
        <Button
          variant="tonal"
          size="sm"
          icon={<AddIcon className="h-4 w-4" />}
          onClick={() => addCell("markdown", null)}
        >
          Markdown
        </Button>
      </div>

      <Dialog
        open={showRun}
        onClose={() => setShowRun(false)}
        title="Executar notebook"
        footer={
          <>
            <Button variant="text" onClick={() => setShowRun(false)}>
              Cancelar
            </Button>
            <Button
              icon={<RunIcon className="h-4 w-4" />}
              loading={execute.isPending}
              onClick={onRun}
            >
              Executar
            </Button>
          </>
        }
      >
        <TextArea
          label="Parâmetros (JSON) — injetados via Papermill"
          rows={5}
          value={paramsText}
          onChange={(e) => {
            setParamsText(e.target.value);
            setParamsError(null);
          }}
          error={
            paramsError ??
            (execute.isError ? (execute.error as Error).message : undefined)
          }
        />
      </Dialog>
    </div>
  );
}
