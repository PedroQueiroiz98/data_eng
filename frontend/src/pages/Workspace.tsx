import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  useBatchDeleteEntries,
  useBatchMoveEntries,
  useCopyEntry,
  useDeleteEntry,
  useGenerateFile,
  useMakeDir,
  useRenameEntry,
  useWorkspace,
  useWorkspaceTree,
  useWriteFile,
} from "@/hooks/useWorkspace";
import { useResizable } from "@/hooks/useResizable";
import { copyText } from "@/lib/clipboard";
import {
  downloadFile,
  executeWorkspaceNotebook,
  getFilePaths,
  uploadFile,
  type FileNode,
} from "@/lib/workspace";
import { downloadExport } from "@/lib/workspaceData";
import {
  baseName,
  dirName,
  joinPath,
  kindFromPath,
  relativeFrom,
} from "@/lib/workspaceFiles";
import { selectView, useWorkspaceStore } from "@/store/workspace";
import { useWorkspaceRuntime } from "@/store/workspaceRuntime";
import { useHotkeys } from "@/hooks/useHotkeys";
import { useAssistantAvailability } from "@/hooks/useAssistant";
import { Palette, type PaletteItem } from "@/components/Palette";
import {
  CreateNotebookDialog,
  type NotebookLanguage,
} from "@/components/workspace/CreateNotebookDialog";
import { EditorSurface } from "@/components/workspace/EditorSurface";
import { EditorTabs } from "@/components/workspace/EditorTabs";
import { ExecutionPanel } from "@/components/workspace/ExecutionPanel";
import { FolderPickerDialog } from "@/components/workspace/FolderPickerDialog";
import { WorkspaceFileBrowser } from "@/components/workspace/WorkspaceFileBrowser";
import { WorkspaceHeader } from "@/components/workspace/WorkspaceHeader";
import { Button, Dialog, EmptyState, TextField, useConfirm, useToast } from "@/ui";
import {
  CollapseIcon,
  ExpandIcon,
  SpinnerIcon,
  WorkspaceIcon,
} from "@/ui/icons";

interface PromptState {
  title: string;
  label: string;
  initial: string;
  confirmLabel: string;
  hint?: string;
  onSubmit: (value: string) => void;
}

function notebookSkeleton(language: NotebookLanguage): Record<string, unknown> {
  const params = {
    cell_type: "code",
    metadata: { tags: ["parameters"] },
    source: "# Parameters\n",
    outputs: [],
    execution_count: null,
  };
  const body =
    language === "sql"
      ? {
          cell_type: "code",
          metadata: {},
          source: "%%sql\nSELECT 1\n",
          outputs: [],
          execution_count: null,
        }
      : { cell_type: "code", metadata: {}, source: "", outputs: [], execution_count: null };
  return {
    nbformat: 4,
    nbformat_minor: 5,
    metadata: {
      kernelspec: { name: "python3", display_name: "Python 3" },
      language_info: { name: "python" },
    },
    cells: [params, body],
  };
}

function flattenFiles(node: FileNode, acc: FileNode[] = []): FileNode[] {
  for (const c of node.children ?? []) {
    if (c.type === "file") acc.push(c);
    else flattenFiles(c, acc);
  }
  return acc;
}

const emitCommand = (cmd: string): void => {
  window.dispatchEvent(new CustomEvent("nbp:workspace-command", { detail: cmd }));
};

export function Workspace() {
  const WS = "root"; // Workspace único (`/root`) — sem seletor/switcher
  const toast = useToast();
  const confirm = useConfirm();
  const navigate = useNavigate();

  const ws = useWorkspace();
  const tree = useWorkspaceTree();
  useAssistantAvailability();

  const setActiveWorkspace = useWorkspaceStore((s) => s.setActiveWorkspace);
  const view = useWorkspaceStore(selectView);
  const dirtyByPath = useWorkspaceStore((s) => s.dirtyByPath);
  const {
    openTab,
    closeTab,
    closeOthers,
    closeToRight,
    closeAll,
    reopenClosed,
    reorderTabs,
    setActiveTab,
    renamePrefix,
    forgetUnder,
    setExpanded,
    toggleDir,
    markDirty,
    setExplorerWidth,
    toggleExplorer,
  } = useWorkspaceStore();

  useEffect(() => {
    setActiveWorkspace(WS);
  }, [setActiveWorkspace]);

  const openPaths = useMemo(() => view.tabs.map((t) => t.path), [view.tabs]);
  const dirtyCount = useMemo(
    () => Object.values(dirtyByPath).filter(Boolean).length,
    [dirtyByPath],
  );

  const writeFile = useWriteFile();
  const makeDir = useMakeDir();
  const rename = useRenameEntry();
  const copy = useCopyEntry();
  const del = useDeleteEntry();
  const generate = useGenerateFile();
  const batchDelete = useBatchDeleteEntries();
  const batchMove = useBatchMoveEntries();

  const [prompt, setPrompt] = useState<PromptState | null>(null);
  const [promptValue, setPromptValue] = useState("");
  const [currentDir, setCurrentDir] = useState("");
  const [nbDialog, setNbDialog] = useState<{ dir: string } | null>(null);
  const [palette, setPalette] = useState<"files" | "commands" | null>(null);
  const [selectedPaths, setSelectedPaths] = useState<Set<string>>(new Set());
  const [movePicker, setMovePicker] = useState<string[] | null>(null);
  const uploadTarget = useRef<string>("");
  const fileInput = useRef<HTMLInputElement>(null);

  const togglePanel = useWorkspaceStore((s) => s.togglePanel);
  const setPanelTab = useWorkspaceStore((s) => s.setPanelTab);
  const kernelStatus = useWorkspaceRuntime((s) => s.kernelStatus);

  const explorerResize = useResizable({
    axis: "x",
    value: view.explorerWidth,
    min: 160,
    max: 560,
    onChange: setExplorerWidth,
  });

  const openPrompt = (p: PromptState) => {
    setPrompt(p);
    setPromptValue(p.initial);
  };

  const onDirtyChange = useCallback(
    (path: string, dirty: boolean) => markDirty(path, dirty),
    [markDirty],
  );

  // ── confirmação de descarte ao fechar aba(s) com alterações pendentes ───────
  const confirmDiscard = useCallback(
    (count: number) => {
      if (count === 0) return Promise.resolve(true);
      return confirm({
        title: "Descartar alterações?",
        message:
          count === 1
            ? "Esta aba tem alterações não salvas. Fechar sem salvar irá descartá-las."
            : `${count} abas têm alterações não salvas. Fechar sem salvar irá descartá-las.`,
        confirmLabel: "Descartar e fechar",
        danger: true,
      });
    },
    [confirm],
  );

  const requestCloseTab = useCallback(
    async (path: string) => {
      if (!(await confirmDiscard(dirtyByPath[path] ? 1 : 0))) return;
      closeTab(path);
    },
    [dirtyByPath, confirmDiscard, closeTab],
  );

  const requestCloseOthers = useCallback(
    async (path: string) => {
      const count = view.tabs.filter((t) => t.path !== path && dirtyByPath[t.path]).length;
      if (!(await confirmDiscard(count))) return;
      closeOthers(path);
    },
    [view.tabs, dirtyByPath, confirmDiscard, closeOthers],
  );

  const requestCloseRight = useCallback(
    async (path: string) => {
      const idx = view.tabs.findIndex((t) => t.path === path);
      const rightTabs = idx >= 0 ? view.tabs.slice(idx + 1) : [];
      const count = rightTabs.filter((t) => dirtyByPath[t.path]).length;
      if (!(await confirmDiscard(count))) return;
      closeToRight(path);
    },
    [view.tabs, dirtyByPath, confirmDiscard, closeToRight],
  );

  const requestCloseAll = useCallback(async () => {
    const count = view.tabs.filter((t) => dirtyByPath[t.path]).length;
    if (!(await confirmDiscard(count))) return;
    closeAll();
  }, [view.tabs, dirtyByPath, confirmDiscard, closeAll]);

  // ── aviso do navegador ao sair com alterações pendentes ─────────────────────
  useEffect(() => {
    const handler = (e: BeforeUnloadEvent) => {
      if (dirtyCount > 0) {
        e.preventDefault();
        e.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [dirtyCount]);

  // ── criação ────────────────────────────────────────────────────────────────
  const createNotebook = (path: string, language: NotebookLanguage) => {
    writeFile.mutate(
      { path, notebook: notebookSkeleton(language) },
      {
        onSuccess: () => {
          setExpanded(dirName(path), true);
          openTab(path, "notebook");
          void tree.refetch();
        },
        onError: (e) => toast.error((e as Error).message),
      },
    );
  };

  const onNewFile = (dir: string) =>
    openPrompt({
      title: "Novo arquivo",
      label: "Nome do arquivo",
      initial: "",
      confirmLabel: "Criar",
      onSubmit: (name) => {
        const path = joinPath(dir, name);
        const isNb = kindFromPath(path) === "notebook";
        writeFile.mutate(
          isNb
            ? { path, notebook: notebookSkeleton("python") }
            : { path, text: "" },
          {
            onSuccess: () => {
              setExpanded(dir, true);
              openTab(path);
              void tree.refetch();
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
        makeDir.mutate(joinPath(dir, name), {
          onSuccess: () => {
            setExpanded(dir, true);
            void tree.refetch();
          },
          onError: (e) => toast.error((e as Error).message),
        }),
    });

  const onGenerateCsv = (dir: string) =>
    openPrompt({
      title: "Gerar CSV de teste",
      label: "Nome do arquivo",
      initial: "bi_data.csv",
      confirmLabel: "Próximo",
      hint: `Será criado em ${dir || "/"} com dados sintéticos gerados no backend.`,
      onSubmit: (name) => {
        const fileName = name.endsWith(".csv") ? name : `${name}.csv`;
        openPrompt({
          title: "Gerar CSV de teste",
          label: "Número de linhas",
          initial: "1000000",
          confirmLabel: "Gerar",
          hint: "Entre 1 e 5.000.000. A geração roda no servidor (streaming em disco).",
          onSubmit: (rowsRaw) => {
            const rows = Number.parseInt(rowsRaw.replace(/\D/g, ""), 10);
            if (!Number.isFinite(rows) || rows < 1) {
              toast.error("Número de linhas inválido.");
              return;
            }
            const path = joinPath(dir, fileName);
            toast.show(`Gerando ${rows.toLocaleString("pt-BR")} linhas…`, "info");
            generate.mutate(
              { path, rows },
              {
                onSuccess: () => {
                  setExpanded(dir, true);
                  void tree.refetch();
                  toast.success(`CSV gerado: ${fileName}`);
                },
                onError: (e) => toast.error((e as Error).message),
              },
            );
          },
        });
      },
    });

  // ── ações de nó ────────────────────────────────────────────────────────────
  const onRename = (node: FileNode) => {
    const parent = dirName(node.path);
    openPrompt({
      title: `Renomear ${node.name}`,
      label: "Novo nome",
      initial: node.name,
      confirmLabel: "Renomear",
      onSubmit: (name) => {
        const clean = name.trim().replace(/\/+/g, "");
        if (!clean || clean === node.name) return;
        const to = joinPath(parent, clean);
        rename.mutate(
          { from: node.path, to },
          {
            onSuccess: () => renamePrefix(node.path, to),
            onError: (e) => toast.error((e as Error).message),
          },
        );
      },
    });
  };

  const onMove = (node: FileNode) => setMovePicker([node.path]);

  const onMoveDrop = async (srcPaths: string[], destDir: string) => {
    const valid = srcPaths.filter(
      (src) => destDir !== dirName(src) && destDir !== src && !destDir.startsWith(`${src}/`),
    );
    if (!valid.length) return;
    const items = valid.map((src) => ({ from: src, to: joinPath(destDir, baseName(src)) }));
    try {
      const { results } = await batchMove.mutateAsync(items);
      const ok = results.filter((r) => r.ok);
      const failed = results.filter((r) => !r.ok);
      for (const r of ok) {
        const to = items.find((it) => it.from === r.path)?.to;
        if (to) renamePrefix(r.path, to);
      }
      if (ok.length && destDir) setExpanded(destDir, true);
      setSelectedPaths(new Set());
      if (failed.length === 0) {
        if (ok.length > 1) toast.success(`${ok.length} item(ns) movido(s).`);
      } else if (ok.length === 0) {
        toast.error(`Falha ao mover: ${failed[0]?.error}`);
      } else {
        toast.error(`${ok.length} movido(s), ${failed.length} falharam.`);
      }
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  const onBatchMove = (paths: string[]) => setMovePicker(paths);

  const onBatchDelete = async (paths: string[]) => {
    const ok = await confirm({
      title: `Excluir ${paths.length} itens?`,
      message: (
        <>
          <p>Os itens abaixo serão removidos. Esta ação não pode ser desfeita.</p>
          <ul className="mt-2 max-h-40 list-disc overflow-auto pl-5 font-mono text-xs">
            {paths.map((p) => (
              <li key={p}>{p}</li>
            ))}
          </ul>
        </>
      ),
      confirmLabel: "Excluir",
      danger: true,
    });
    if (!ok) return;
    try {
      const { results } = await batchDelete.mutateAsync({ paths, recursive: true });
      const okPaths = results.filter((r) => r.ok).map((r) => r.path);
      const failed = results.filter((r) => !r.ok);
      for (const p of okPaths) {
        for (const tab of openPaths) {
          if (tab === p || tab.startsWith(`${p}/`)) closeTab(tab, { forget: true });
        }
        forgetUnder(p);
      }
      setSelectedPaths(new Set());
      if (failed.length === 0) {
        toast.success(`${okPaths.length} item(ns) excluído(s).`);
      } else if (okPaths.length === 0) {
        toast.error(`Falha ao excluir: ${failed[0]?.error}`);
      } else {
        toast.error(`${okPaths.length} excluído(s), ${failed.length} falharam.`);
      }
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  const onDuplicate = async (node: FileNode) => {
    const parent = dirName(node.path);
    const dot = node.name.lastIndexOf(".");
    const stem = dot > 0 ? node.name.slice(0, dot) : node.name;
    const suffix = dot > 0 ? node.name.slice(dot) : "";
    // 1ª tentativa: "<nome> copy.<ext>"; em colisão: "<nome> copy 2.<ext>", …
    for (let i = 1; i <= 50; i++) {
      const candidate = `${stem} copy${i === 1 ? "" : ` ${i}`}${suffix}`;
      const to = joinPath(parent, candidate);
      try {
        await copy.mutateAsync({ from: node.path, to });
        setExpanded(parent, true);
        void tree.refetch();
        if (node.type === "file") openTab(to);
        toast.success(`Duplicado: ${candidate}`);
        return;
      } catch (e) {
        const err = e as { code?: string; status?: number; message?: string };
        const isConflict = err.status === 409 || err.code === "CONFLICT";
        if (!isConflict) {
          toast.error(err.message ?? "Não foi possível duplicar.");
          return;
        }
        // colisão → tenta o próximo sufixo
      }
    }
    toast.error("Não foi possível encontrar um nome livre para a cópia.");
  };

  const onDelete = async (node: FileNode) => {
    const ok = await confirm({
      title: `Excluir ${node.name}?`,
      message:
        (node.type === "dir"
          ? `A pasta "${node.path}" e todo o seu conteúdo serão removidos. `
          : `O arquivo "${node.path}" será removido. `) +
        "Esta ação não pode ser desfeita.",
      confirmLabel: "Excluir",
      danger: true,
    });
    if (!ok) return;
    del.mutate(
      { path: node.path, recursive: node.type === "dir" },
      {
        onSuccess: () => {
          for (const p of openPaths) {
            if (p === node.path || p.startsWith(`${node.path}/`)) {
              closeTab(p, { forget: true });
            }
          }
          forgetUnder(node.path);
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
      await uploadFile(uploadTarget.current, file);
      setExpanded(uploadTarget.current, true);
      void tree.refetch();
      toast.success(`Enviado: ${file.name}`);
    } catch (err) {
      toast.error((err as Error).message);
    }
  };

  const onDownload = async (node: FileNode) => {
    try {
      await downloadFile(node.path);
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  const onCopyPath = async (
    node: FileNode,
    kind: "path" | "relative" | "repo" | "read-example",
  ) => {
    let value: string | null = null;
    try {
      if (kind === "relative") {
        value = view.activeTab
          ? relativeFrom(view.activeTab, node.path)
          : node.path;
      } else {
        const info = await getFilePaths(node.path, view.activeTab ?? undefined);
        value =
          kind === "repo"
            ? info.repository_path
            : kind === "read-example"
              ? info.read_example
              : info.workspace_path;
      }
    } catch (e) {
      toast.error((e as Error).message);
      return;
    }
    if (!value) {
      toast.error("Sem exemplo de leitura para este tipo de arquivo.");
      return;
    }
    if (await copyText(value)) toast.success("Caminho copiado");
    else toast.error("Não foi possível copiar");
  };

  const onRun = async (node: FileNode) => {
    try {
      const exec = await executeWorkspaceNotebook(node.path);
      toast.success("Execução iniciada");
      navigate(`/executions/${exec.id}`);
    } catch (err) {
      toast.error((err as Error).message);
    }
  };

  const onExport = async (node: FileNode) => {
    try {
      // Notebook → exporta como .py (nbconvert). Para .ipynb cru use "Baixar".
      await downloadExport(WS, node.path, "py");
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  const fileItems: PaletteItem[] = useMemo(
    () =>
      tree.data
        ? flattenFiles(tree.data).map((f) => ({
            id: f.path,
            label: baseName(f.path),
            sublabel: dirName(f.path) || "/",
          }))
        : [],
    [tree.data],
  );

  const commandItems: PaletteItem[] = useMemo(
    () => [
      { id: "cmd:new-notebook", label: "Criar notebook" },
      { id: "cmd:new-python", label: "Criar arquivo Python" },
      { id: "cmd:new-sql", label: "Criar arquivo SQL" },
      { id: "cmd:new-markdown", label: "Criar Markdown" },
      { id: "cmd:new-folder", label: "Criar pasta" },
      { id: "cmd:open-file", label: "Abrir arquivo…", sublabel: "Ctrl+P" },
      { id: "cmd:run-all", label: "Executar todas as células" },
      { id: "cmd:restart-kernel", label: "Reiniciar kernel" },
      { id: "cmd:interrupt-kernel", label: "Interromper kernel" },
      { id: "cmd:save", label: "Salvar notebook", sublabel: "Ctrl+S" },
      { id: "cmd:clear-outputs", label: "Limpar saídas" },
      { id: "cmd:create-workflow", label: "Criar Workflow do notebook" },
      { id: "cmd:git", label: "Git: abrir painel de alterações" },
      { id: "cmd:toggle-panel", label: "Alternar painel inferior", sublabel: "Ctrl+J" },
      { id: "cmd:toggle-explorer", label: "Alternar explorer", sublabel: "Ctrl+B" },
      { id: "cmd:close-tab", label: "Fechar aba" },
      { id: "cmd:reopen-tab", label: "Reabrir aba fechada" },
    ],
    [],
  );

  const runCommand = (cmdId: string): void => {
    switch (cmdId) {
      case "cmd:new-notebook":
        setNbDialog({ dir: view.activeTab ? dirName(view.activeTab) : "" });
        break;
      case "cmd:new-folder":
        onNewFolder("");
        break;
      case "cmd:new-python":
      case "cmd:new-sql":
      case "cmd:new-markdown": {
        const ext = cmdId.endsWith("python")
          ? ".py"
          : cmdId.endsWith("sql")
            ? ".sql"
            : ".md";
        const dir = view.activeTab ? dirName(view.activeTab) : "";
        openPrompt({
          title: `Novo arquivo ${ext}`,
          label: "Nome do arquivo",
          initial: `novo${ext}`,
          confirmLabel: "Criar",
          onSubmit: (n) => {
            const nm = n.endsWith(ext) ? n : `${n}${ext}`;
            const p = joinPath(dir, nm);
            writeFile.mutate(
              { path: p, text: "" },
              { onSuccess: () => openTab(p), onError: (e) => toast.error((e as Error).message) },
            );
          },
        });
        break;
      }
      case "cmd:open-file":
        setPalette("files");
        break;
      case "cmd:run-all":
      case "cmd:restart-kernel":
      case "cmd:interrupt-kernel":
      case "cmd:save":
      case "cmd:clear-outputs":
      case "cmd:create-workflow":
        emitCommand(cmdId.replace("cmd:", ""));
        break;
      case "cmd:git":
        setPanelTab("git");
        break;
      case "cmd:toggle-panel":
        togglePanel();
        break;
      case "cmd:toggle-explorer":
        toggleExplorer();
        break;
      case "cmd:close-tab":
        if (view.activeTab) void requestCloseTab(view.activeTab);
        break;
      case "cmd:reopen-tab":
        reopenClosed();
        break;
    }
  };

  useHotkeys({
    "mod+p": () => setPalette("files"),
    "mod+shift+p": () => setPalette("commands"),
    "mod+b": () => toggleExplorer(),
    "mod+j": () => togglePanel(),
  });

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

  const iconBtn =
    "rounded p-1 text-fg-faint hover:bg-surface-variant hover:text-fg";

  return (
    <div className="flex min-w-0 flex-1 flex-col">
      <WorkspaceHeader workspace={ws.data} dirtyCount={dirtyCount} />

      <div className="flex min-h-0 flex-1">
        {/* Explorer */}
        {view.explorerCollapsed ? (
          <button
            type="button"
            title="Mostrar explorer"
            className="flex w-8 shrink-0 items-start justify-center border-r border-surface-border bg-surface pt-2"
            onClick={() => toggleExplorer(true)}
          >
            <ExpandIcon className="h-4 w-4 text-fg-faint" />
          </button>
        ) : (
          <>
            <aside
              className="flex shrink-0 flex-col border-r border-surface-border bg-surface"
              style={{ width: view.explorerWidth }}
            >
              <div className="flex h-9 items-center justify-between px-2 text-[11px] font-semibold uppercase tracking-wide text-fg-faint">
                Home
                <button
                  type="button"
                  className={iconBtn}
                  title="Ocultar explorer"
                  onClick={() => toggleExplorer(false)}
                >
                  <CollapseIcon className="h-4 w-4 rotate-180" />
                </button>
              </div>

              <WorkspaceFileBrowser
                root={tree.data}
                loading={tree.isLoading}
                currentDir={currentDir}
                setCurrentDir={setCurrentDir}
                expandedDirs={view.expandedDirs}
                onToggleDir={toggleDir}
                openPaths={openPaths}
                activePath={view.activeTab}
                dirtyPaths={dirtyByPath}
                onRefresh={() => void tree.refetch()}
                onOpenFile={(path) => openTab(path)}
                onNewNotebook={(dir) => setNbDialog({ dir })}
                onNewFile={onNewFile}
                onNewFolder={onNewFolder}
                onUpload={onUpload}
                onGenerateCsv={onGenerateCsv}
                onRename={onRename}
                onMove={onMove}
                onDuplicate={onDuplicate}
                onDelete={onDelete}
                onDownload={onDownload}
                onCopyPath={onCopyPath}
                onRun={onRun}
                onExport={onExport}
                onMoveDrop={onMoveDrop}
                selectedPaths={selectedPaths}
                onSelectionChange={setSelectedPaths}
                onBatchMove={onBatchMove}
                onBatchDelete={onBatchDelete}
              />
            </aside>
            <div
              {...explorerResize.handleProps}
              className={`w-1 shrink-0 cursor-col-resize bg-surface-border transition-colors hover:bg-primary/40 ${
                explorerResize.dragging ? "bg-primary/60" : ""
              }`}
            />
          </>
        )}

        {/* Editor */}
        <section className="flex min-w-0 flex-1 flex-col bg-surface">
          {view.tabs.length > 0 && (
            <EditorTabs
              tabs={view.tabs}
              activeTab={view.activeTab}
              dirtyByPath={dirtyByPath}
              onSelect={setActiveTab}
              onClose={(path) => void requestCloseTab(path)}
              onCloseOthers={(path) => void requestCloseOthers(path)}
              onCloseRight={(path) => void requestCloseRight(path)}
              onCloseAll={() => void requestCloseAll()}
              onReopen={reopenClosed}
              onReorder={reorderTabs}
            />
          )}
          <EditorSurface
            workspaceId={WS}
            tabs={view.tabs}
            activeTab={view.activeTab}
            onDirtyChange={onDirtyChange}
          />
        </section>
      </div>

      <ExecutionPanel workspaceId={WS} />

      <div className="flex h-6 shrink-0 items-center gap-3 border-t border-surface-border bg-surface px-3 text-[11px] text-fg-faint">
        <span>{ws.data.name}</span>
        <span>·</span>
        <span>Kernel: {kernelStatus}</span>
        {dirtyCount > 0 && (
          <span className="text-warn">{dirtyCount} não salvo(s)</span>
        )}
        <span className="ml-auto">{view.activeTab ?? "—"}</span>
      </div>

      <Palette
        open={palette === "files"}
        placeholder="Buscar arquivos…"
        items={fileItems}
        onPick={(path) => openTab(path)}
        onClose={() => setPalette(null)}
      />
      <Palette
        open={palette === "commands"}
        placeholder="Executar comando…"
        items={commandItems}
        onPick={runCommand}
        onClose={() => setPalette(null)}
      />

      <input
        ref={fileInput}
        type="file"
        className="hidden"
        onChange={(e) => void onFilePicked(e)}
      />

      <CreateNotebookDialog
        open={!!nbDialog}
        defaultDir={nbDialog?.dir ?? ""}
        onClose={() => setNbDialog(null)}
        onCreate={createNotebook}
      />

      <FolderPickerDialog
        open={!!movePicker}
        root={tree.data}
        excludePrefixes={movePicker ?? []}
        initialDir={movePicker?.length === 1 ? dirName(movePicker[0] ?? "") : ""}
        onClose={() => setMovePicker(null)}
        onConfirm={(destDir) => {
          if (movePicker) void onMoveDrop(movePicker, destDir);
        }}
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
          hint={prompt?.hint}
          onChange={(e) => setPromptValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              prompt?.onSubmit(promptValue.trim());
              setPrompt(null);
            }
          }}
        />
      </Dialog>
    </div>
  );
}
