import { useEffect, useMemo, useState } from "react";
import Editor from "@monaco-editor/react";
import { useTheme } from "@/components/ThemeProvider";
import { useWorkspaceFile, useWriteFile } from "@/hooks/useWorkspace";
import { downloadUrl } from "@/lib/workspace";
import { Button } from "@/ui";
import { DownloadIcon, SaveIcon, SpinnerIcon } from "@/ui/icons";

interface Props {
  workspaceId: string;
  path: string;
  onDirtyChange: (path: string, dirty: boolean) => void;
}

const LANG_BY_EXT: Record<string, string> = {
  py: "python",
  js: "javascript",
  ts: "typescript",
  tsx: "typescript",
  jsx: "javascript",
  json: "json",
  ipynb: "json",
  md: "markdown",
  txt: "plaintext",
  yml: "yaml",
  yaml: "yaml",
  toml: "ini",
  cfg: "ini",
  ini: "ini",
  sql: "sql",
  sh: "shell",
  csv: "plaintext",
};

function langFor(path: string): string {
  const ext = path.split(".").pop()?.toLowerCase() ?? "";
  return LANG_BY_EXT[ext] ?? "plaintext";
}

export function FilePreview({ workspaceId, path, onDirtyChange }: Props) {
  const { theme } = useTheme();
  const { data, isLoading, isError, error } = useWorkspaceFile(workspaceId, path);
  const save = useWriteFile(workspaceId);

  const [draft, setDraft] = useState<string | null>(null);
  const original = useMemo(() => {
    if (!data) return "";
    if (data.kind === "notebook") return JSON.stringify(data.content, null, 1);
    if (data.kind === "text") return (data.content as string) ?? "";
    return "";
  }, [data]);

  useEffect(() => {
    setDraft(null);
    onDirtyChange(path, false);
  }, [path, onDirtyChange]);

  const dirty = draft != null && draft !== original;
  useEffect(() => {
    onDirtyChange(path, dirty);
  }, [dirty, path, onDirtyChange]);

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center text-fg-faint">
        <SpinnerIcon className="h-5 w-5 animate-spin" />
      </div>
    );
  }
  if (isError) {
    return (
      <div className="p-6 text-sm text-danger">
        Falha ao abrir o arquivo: {(error as Error)?.message}
      </div>
    );
  }
  if (!data) return null;

  if (data.kind === "binary") {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center">
        <p className="text-sm text-fg-muted">
          Arquivo binário — não pode ser editado no navegador.
        </p>
        <a href={downloadUrl(workspaceId, path)} target="_blank" rel="noreferrer">
          <Button size="sm" icon={<DownloadIcon className="h-4 w-4" />}>
            Baixar {path.split("/").pop()}
          </Button>
        </a>
      </div>
    );
  }

  const value = draft ?? original;
  const isNotebook = data.kind === "notebook";

  const onSave = async () => {
    if (!dirty) return;
    try {
      if (isNotebook) {
        await save.mutateAsync({ path, notebook: JSON.parse(value) as Record<string, unknown> });
      } else {
        await save.mutateAsync({ path, text: value });
      }
      setDraft(null);
      onDirtyChange(path, false);
    } catch {
      // erro fica visível no botão via save.isError; toast tratado pelo caller se quiser
    }
  };

  return (
    <div className="flex h-full flex-col">
      <div className="flex h-10 shrink-0 items-center gap-2 border-b border-surface-border px-3 text-xs text-fg-muted">
        <span className="truncate">{path}</span>
        {isNotebook && (
          <span className="rounded bg-surface-variant px-1.5 py-0.5 text-[10px]">
            notebook (JSON)
          </span>
        )}
        {dirty && <span className="text-amber-600 dark:text-amber-400">• modificado</span>}
        <div className="ml-auto flex items-center gap-1">
          <a href={downloadUrl(workspaceId, path)} target="_blank" rel="noreferrer">
            <Button size="sm" variant="text" icon={<DownloadIcon className="h-4 w-4" />}>
              Baixar
            </Button>
          </a>
          <Button
            size="sm"
            icon={<SaveIcon className="h-4 w-4" />}
            disabled={!dirty}
            loading={save.isPending}
            onClick={() => void onSave()}
          >
            Salvar
          </Button>
        </div>
      </div>
      {save.isError && (
        <div className="border-b border-surface-border bg-danger/10 px-3 py-1 text-xs text-danger">
          {(save.error as Error).message}
        </div>
      )}
      <div className="min-h-0 flex-1">
        <Editor
          value={value}
          language={langFor(path)}
          theme={theme === "dark" ? "vs-dark" : "vs"}
          onChange={(v) => setDraft(v ?? "")}
          options={{
            minimap: { enabled: false },
            fontSize: 13,
            scrollBeyondLastLine: false,
            automaticLayout: true,
            tabSize: 2,
          }}
        />
      </div>
    </div>
  );
}
