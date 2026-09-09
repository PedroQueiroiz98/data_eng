import { useCallback, useEffect, useMemo, useState } from "react";
import Editor from "@monaco-editor/react";
import { useTheme } from "@/components/ThemeProvider";
import { useHotkeys } from "@/hooks/useHotkeys";
import { useWorkspaceFile, useWriteFile } from "@/hooks/useWorkspace";
import { downloadFile } from "@/lib/workspace";
import { Button, useToast } from "@/ui";
import { DownloadIcon, SaveIcon, SpinnerIcon } from "@/ui/icons";

interface Props {
  path: string;
  onDirtyChange: (path: string, dirty: boolean) => void;
  active?: boolean;
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

export function FilePreview({ path, onDirtyChange, active = true }: Props) {
  const { theme } = useTheme();
  const toast = useToast();
  const { data, isLoading, isError, error } = useWorkspaceFile(path);
  const save = useWriteFile();

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

  const value = draft ?? original;
  const isNotebook = data?.kind === "notebook";

  const onSave = useCallback(async () => {
    if (draft == null || draft === original) return;
    try {
      if (isNotebook) {
        await save.mutateAsync({
          path,
          notebook: JSON.parse(draft) as Record<string, unknown>,
        });
      } else {
        await save.mutateAsync({ path, text: draft });
      }
      setDraft(null);
      onDirtyChange(path, false);
      toast.success("Salvo");
    } catch (e) {
      toast.error(`Não foi possível salvar: ${(e as Error).message}`);
    }
  }, [draft, original, isNotebook, save, path, onDirtyChange, toast]);

  // Ctrl/Cmd+S salva o arquivo de texto/código (só a aba ativa).
  useHotkeys({ "mod+s": () => void onSave() }, active && data?.kind !== "binary");

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
        <Button
          size="sm"
          icon={<DownloadIcon className="h-4 w-4" />}
          onClick={() => {
            void downloadFile(path).catch((e) =>
              toast.error((e as Error).message),
            );
          }}
        >
          Baixar {path.split("/").pop()}
        </Button>
      </div>
    );
  }

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
          <Button
            size="sm"
            variant="text"
            icon={<DownloadIcon className="h-4 w-4" />}
            onClick={() => {
              void downloadFile(path).catch((e) =>
                toast.error((e as Error).message),
              );
            }}
          >
            Baixar
          </Button>
          <Button
            size="sm"
            icon={<SaveIcon className="h-4 w-4" />}
            disabled={!dirty}
            loading={save.isPending}
            onClick={() => void onSave()}
          >
            {save.isPending ? "Salvando…" : "Salvar"}
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
