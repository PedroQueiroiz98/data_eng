import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import {
  useDeleteEntry,
  useMakeDir,
  useRenameEntry,
  useWorkspace,
  useWorkspaceTree,
  useWriteFile,
} from "@/hooks/useWorkspace";
import { downloadUrl, uploadFile, type FileNode } from "@/lib/workspace";
import { useWorkspaceStore } from "@/store/workspace";
import { FilePreview } from "@/components/workspace/FilePreview";
import { FileTree } from "@/components/workspace/FileTree";
import { WorkspaceHeader } from "@/components/workspace/WorkspaceHeader";
import { Button, Dialog, EmptyState, TextField, useConfirm, useToast } from "@/ui";
import { SpinnerIcon, WorkspaceIcon } from "@/ui/icons";

interface PromptState {
  title: string;
  label: string;
  initial: string;
  confirmLabel: string;
  onSubmit: (value: string) => void;
}

export function Workspace() {
  const { id = "" } = useParams();
  const toast = useToast();
  const confirm = useConfirm();

  const ws = useWorkspace(id);
  const tree = useWorkspaceTree(id);

  const {
    openPath,
    expandedDirs,
    dirtyByPath,
    setActiveWorkspace,
    openFile,
    toggleDir,
    setExpanded,
    markDirty,
  } = useWorkspaceStore();

  useEffect(() => {
    setActiveWorkspace(id);
  }, [id, setActiveWorkspace]);

  const dirtyCount = useMemo(
    () => Object.values(dirtyByPath).filter(Boolean).length,
    [dirtyByPath],
  );

  const writeFile = useWriteFile(id);
  const makeDir = useMakeDir(id);
  const rename = useRenameEntry(id);
  const del = useDeleteEntry(id);

  const [prompt, setPrompt] = useState<PromptState | null>(null);
  const [promptValue, setPromptValue] = useState("");
  const uploadTarget = useRef<string>("");
  const fileInput = useRef<HTMLInputElement>(null);

  const openPrompt = (p: PromptState) => {
    setPrompt(p);
    setPromptValue(p.initial);
  };

  const join = (dir: string, name: string) => (dir ? `${dir}/${name}` : name);

  const onNewFile = (dir: string) =>
    openPrompt({
      title: "Novo arquivo",
      label: "Nome do arquivo",
      initial: "",
      confirmLabel: "Criar",
      onSubmit: (name) => {
        const path = join(dir, name);
        const isNb = name.toLowerCase().endsWith(".ipynb");
        writeFile.mutate(
          isNb
            ? {
                path,
                notebook: {
                  nbformat: 4,
                  nbformat_minor: 5,
                  metadata: {
                    kernelspec: { name: "python3", display_name: "Python 3" },
                    language_info: { name: "python" },
                  },
                  cells: [
                    {
                      cell_type: "code",
                      metadata: { tags: ["parameters"] },
                      source: "# Parameters\n",
                      outputs: [],
                      execution_count: null,
                    },
                  ],
                },
              }
            : { path, text: "" },
          {
            onSuccess: () => {
              setExpanded(dir, true);
              openFile(path);
            },
            onError: (e) => toast.error((e as Error).message),
          },
        );
      },
    });

  const onNewFolder = (dir: string) =>
    openPrompt({
      title: "Nova pasta",
      label: "Nome da pasta",
      initial: "",
      confirmLabel: "Criar",
      onSubmit: (name) =>
        makeDir.mutate(join(dir, name), {
          onSuccess: () => setExpanded(dir, true),
          onError: (e) => toast.error((e as Error).message),
        }),
    });

  const onRename = (node: FileNode) => {
    const parent = node.path.includes("/")
      ? node.path.slice(0, node.path.lastIndexOf("/"))
      : "";
    openPrompt({
      title: `Renomear ${node.name}`,
      label: "Novo nome",
      initial: node.name,
      confirmLabel: "Renomear",
      onSubmit: (name) =>
        rename.mutate(
          { from: node.path, to: join(parent, name) },
          {
            onSuccess: () => {
              if (openPath === node.path) openFile(join(parent, name));
            },
            onError: (e) => toast.error((e as Error).message),
          },
        ),
    });
  };

  const onDelete = async (node: FileNode) => {
    const ok = await confirm({
      title: `Excluir ${node.name}`,
      message:
        node.type === "dir"
          ? `Excluir a pasta "${node.path}" e todo o seu conteúdo?`
          : `Excluir o arquivo "${node.path}"?`,
      confirmLabel: "Excluir",
      danger: true,
    });
    if (!ok) return;
    del.mutate(
      { path: node.path, recursive: node.type === "dir" },
      {
        onSuccess: () => {
          if (openPath === node.path) openFile("");
          if (openPath && openPath.startsWith(`${node.path}/`)) openFile("");
        },
        onError: (e) => toast.error((e as Error).message),
      },
    );
  };

  const onUpload = (dir: string) => {
    uploadTarget.current = dir;
    fileInput.current?.click();
  };

  const onFilePicked = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    try {
      await uploadFile(id, uploadTarget.current, file);
      setExpanded(uploadTarget.current, true);
      void tree.refetch();
      toast.success(`Enviado: ${file.name}`);
    } catch (err) {
      toast.error((err as Error).message);
    }
  };

  const onDownload = (node: FileNode) => {
    window.open(downloadUrl(id, node.path), "_blank");
  };

  const onDirtyChange = useCallback(
    (path: string, dirty: boolean) => markDirty(path, dirty),
    [markDirty],
  );

  if (ws.isLoading) {
    return (
      <div className="flex h-full flex-1 items-center justify-center text-fg-faint">
        <SpinnerIcon className="h-6 w-6 animate-spin" />
      </div>
    );
  }
  if (ws.isError || !ws.data) {
    return (
      <div className="flex-1 p-8">
        <EmptyState
          icon={WorkspaceIcon}
          title="Workspace não encontrado"
          description="Ele pode ter sido removido ou você não tem acesso."
        />
      </div>
    );
  }

  return (
    <div className="flex min-w-0 flex-1 flex-col">
      <WorkspaceHeader workspace={ws.data} dirtyCount={dirtyCount} />

      <div className="flex min-h-0 flex-1">
        {/* Explorer */}
        <aside className="flex w-64 shrink-0 flex-col border-r border-surface-border bg-surface">
          <div className="flex h-9 items-center justify-between px-3 text-[11px] font-semibold uppercase tracking-wide text-fg-faint">
            Explorer
            <span className="flex gap-1">
              <button
                type="button"
                className="rounded px-1 hover:bg-surface-variant"
                title="Novo arquivo na raiz"
                onClick={() => onNewFile("")}
              >
                +arq
              </button>
              <button
                type="button"
                className="rounded px-1 hover:bg-surface-variant"
                title="Nova pasta na raiz"
                onClick={() => onNewFolder("")}
              >
                +dir
              </button>
            </span>
          </div>
          <div className="min-h-0 flex-1 overflow-auto">
            {tree.isLoading ? (
              <div className="flex justify-center py-6 text-fg-faint">
                <SpinnerIcon className="h-4 w-4 animate-spin" />
              </div>
            ) : tree.data ? (
              <FileTree
                root={tree.data}
                openPath={openPath}
                expanded={expandedDirs}
                onToggleDir={toggleDir}
                onOpenFile={openFile}
                onNewFile={onNewFile}
                onNewFolder={onNewFolder}
                onRename={onRename}
                onDelete={onDelete}
                onUpload={onUpload}
                onDownload={onDownload}
              />
            ) : (
              <p className="px-3 py-2 text-xs text-danger">Falha ao carregar a árvore.</p>
            )}
          </div>
        </aside>

        {/* Editor */}
        <section className="flex min-w-0 flex-1 flex-col bg-surface">
          {openPath ? (
            <FilePreview
              key={openPath}
              workspaceId={id}
              path={openPath}
              onDirtyChange={onDirtyChange}
            />
          ) : (
            <div className="flex flex-1 items-center justify-center">
              <EmptyState
                icon={WorkspaceIcon}
                title="Nenhum arquivo aberto"
                description="Escolha um arquivo no explorer para editar."
              />
            </div>
          )}
        </section>
      </div>

      <input
        ref={fileInput}
        type="file"
        className="hidden"
        onChange={(e) => void onFilePicked(e)}
      />

      <Dialog
        open={!!prompt}
        onClose={() => setPrompt(null)}
        title={prompt?.title ?? ""}
        footer={
          <>
            <Button variant="text" onClick={() => setPrompt(null)}>
              Cancelar
            </Button>
            <Button
              disabled={!promptValue.trim()}
              onClick={() => {
                const v = promptValue.trim();
                if (!v) return;
                prompt?.onSubmit(v);
                setPrompt(null);
              }}
            >
              {prompt?.confirmLabel ?? "OK"}
            </Button>
          </>
        }
      >
        <TextField
          label={prompt?.label ?? "Nome"}
          value={promptValue}
          autoFocus
          onChange={(e) => setPromptValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && promptValue.trim()) {
              prompt?.onSubmit(promptValue.trim());
              setPrompt(null);
            }
          }}
        />
      </Dialog>
    </div>
  );
}
