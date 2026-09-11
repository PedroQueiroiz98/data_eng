import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import type * as monacoNS from "monaco-editor";
import { useTheme } from "@/components/ThemeProvider";
import { CreateWorkflowDialog } from "@/components/workspace/CreateWorkflowDialog";
import { LocationsPanel } from "@/components/notebook/LocationsPanel";
import { ProblemsPanel } from "@/components/notebook/ProblemsPanel";
import { WorkspaceCell } from "@/components/workspace/notebook/WorkspaceCell";
import { useAutosave } from "@/hooks/useAutosave";
import { useHotkeys } from "@/hooks/useHotkeys";
import { useKernel } from "@/hooks/useKernel";
import { useWorkspaceFile, useWorkspaceTree, useWriteFile } from "@/hooks/useWorkspace";
import { useEditorConfig } from "@/lib/editorConfig";
import type { KernelEvent } from "@/lib/kernels";
import { lspDiagnostics, type LspDiagnostic, type LspLocation } from "@/lib/lsp";
import { wsCellModelPath } from "@/lib/lspShared";
import { setLspDoc, setLspKernel } from "@/lib/monacoProviders";
import { setWorkspaceFsContext } from "@/lib/monacoProviders";
import { assistantStream } from "@/lib/assistant";
import { setNotebookAiContext } from "@/lib/assistantContext";
import { useAssistantStore } from "@/store/assistant";
import type { AiCommandDetail } from "@/components/assistant/AiCellMenu";
import type { NotebookContent } from "@/lib/notebooks";
import type { FileNode } from "@/lib/workspace";
import { downloadExport } from "@/lib/workspaceData";
import { relativeFrom } from "@/lib/workspaceFiles";
import { useWorkspaceStore } from "@/store/workspace";
import { useWorkspaceRuntime } from "@/store/workspaceRuntime";
import {
  emptyState,
  reducer,
  toContent,
  type WNotebookState,
} from "@/store/workspaceNotebook";
import { Button, useToast } from "@/ui";
import {
  AddIcon,
  DownloadIcon,
  RetryIcon,
  RunIcon,
  SaveIcon,
  SpinnerIcon,
  StopIcon,
} from "@/ui/icons";

type SaveState = "saved" | "saving" | "dirty" | "error";

const KERNEL_LABEL: Record<string, string> = {
  starting: "iniciando",
  idle: "pronto",
  busy: "ocupado",
  restarting: "reiniciando",
  dead: "morto",
};

interface Props {
  workspaceId: string;
  path: string;
  active: boolean;
  onDirtyChange: (path: string, dirty: boolean) => void;
}

export function WorkspaceNotebookEditor({
  workspaceId,
  path,
  active,
  onDirtyChange,
}: Props) {
  const { theme } = useTheme();
  const toast = useToast();
  const navigate = useNavigate();
  const [wfDialog, setWfDialog] = useState(false);
  const file = useWorkspaceFile(path);
  const write = useWriteFile();
  const autosave = useWorkspaceStore((s) => s.autosave);
  const setPanelTab = useWorkspaceStore((s) => s.setPanelTab);

  const [state, dispatch] = useReducer(reducer, emptyState);
  const stateRef = useRef<WNotebookState>(state);
  stateRef.current = state;

  const etagRef = useRef<string | null>(null);
  const savedJson = useRef<string>("");
  const [saveState, setSaveState] = useState<SaveState>("saved");
  const [focusedCell, setFocusedCell] = useState<string | null>(null);
  const [runAll, setRunAll] = useState<{ done: number; total: number } | null>(null);

  // ── LSP (autocomplete/diagnostics/go-to-def) ───────────────────────────────
  const editorsRef = useRef<
    Map<number, monacoNS.editor.IStandaloneCodeEditor>
  >(new Map());
  const [diags, setDiags] = useState<LspDiagnostic[]>([]);
  const [locPanel, setLocPanel] = useState<{
    title: string;
    locations: LspLocation[];
  } | null>(null);
  const [showProblems, setShowProblems] = useState(false);
  const diagnosticsEnabled = useEditorConfig((s) => s.config.editor.diagnostics);
  const tree = useWorkspaceTree();

  const lspCtx = useCallback(
    () => ({ workspaceId, notebookPath: path }),
    [workspaceId, path],
  );

  const navigateToCell = useCallback(
    (cellIndex: number, line: number, column: number) => {
      const ed = editorsRef.current.get(cellIndex);
      if (!ed) return;
      ed.getContainerDomNode()?.scrollIntoView({ block: "center", behavior: "smooth" });
      ed.setPosition({ lineNumber: line + 1, column: column + 1 });
      ed.revealPositionInCenter({ lineNumber: line + 1, column: column + 1 });
      ed.focus();
      setLocPanel(null);
    },
    [],
  );

  const registerEditor = useCallback(
    (i: number, ed: monacoNS.editor.IStandaloneCodeEditor | null) => {
      if (ed) editorsRef.current.set(i, ed);
      else editorsRef.current.delete(i);
    },
    [],
  );

  // ── carregar o arquivo uma vez ─────────────────────────────────────────────
  const loadedFor = useRef<string | null>(null);
  useEffect(() => {
    if (!file.data || file.data.kind !== "notebook") return;
    if (loadedFor.current === path) return;
    loadedFor.current = path;
    const content = file.data.content as unknown as NotebookContent;
    dispatch({ type: "load", content });
    etagRef.current = file.data.etag ?? null;
    savedJson.current = JSON.stringify(content);
    setSaveState("saved");
  }, [file.data, path]);

  // ── dirty tracking ────────────────────────────────────────────────────────
  const currentJson = useMemo(
    () => (state.loaded ? JSON.stringify(toContent(state)) : ""),
    [state],
  );
  const dirty = state.loaded && currentJson !== savedJson.current;
  useEffect(() => {
    onDirtyChange(path, dirty);
    setSaveState((s) => (dirty ? (s === "saving" ? "saving" : "dirty") : s === "error" ? "error" : "saved"));
  }, [dirty, path, onDirtyChange]);

  // ── kernel ────────────────────────────────────────────────────────────────
  const onKernelEvent = useCallback((e: KernelEvent) => {
    useWorkspaceRuntime.getState().ingest(e);
    if (!e.cell_id) return;
    if (e.type === "cell.started") {
      dispatch({ type: "runStart", id: e.cell_id });
      useAssistantStore.getState().setCellError(e.cell_id, null);
    } else if ((e.type === "cell.output" || e.type === "cell.error") && e.output) {
      dispatch({ type: "cellOutput", id: e.cell_id, output: e.output });
      if (e.type === "cell.error" && e.output.output_type === "error") {
        useAssistantStore.getState().setCellError(e.cell_id, {
          ename: e.output.ename ?? "",
          evalue: e.output.evalue ?? "",
          traceback: e.output.traceback ?? [],
        });
      }
    } else if (e.type === "cell.finished") {
      dispatch({
        type: "runFinish",
        id: e.cell_id,
        status: e.status === "error" ? "error" : "ok",
        execution_count: e.execution_count ?? null,
        durationMs: e.duration_ms,
        outputs: e.outputs,
      });
      if (e.status === "error") setPanelTab("execution");
    }
  }, [setPanelTab]);

  const kernel = useKernel(workspaceId, path, onKernelEvent);
  const kernelStatusRef = useRef(kernel.status);
  kernelStatusRef.current = kernel.status;

  useEffect(() => {
    if (active) {
      useWorkspaceRuntime.getState().setKernel(kernel.status, kernel.connected);
    }
  }, [active, kernel.status, kernel.connected]);

  // publica a sessão de kernel p/ o autocomplete ciente de objetos vivos
  useEffect(() => {
    if (!active || !kernel.sessionId) {
      setLspKernel(null);
      return;
    }
    setLspKernel({ sessionId: kernel.sessionId, status: kernel.status });
    return () => setLspKernel(null);
  }, [active, kernel.sessionId, kernel.status]);

  // publica o "documento lógico" para os providers do Monaco (só a aba ativa)
  const cellIds = state.cells.map((c) => c.id).join(",");
  useEffect(() => {
    if (!active) return;
    setLspDoc({
      cellUris: stateRef.current.cells.map((c) =>
        wsCellModelPath(workspaceId, path, c.id),
      ),
      getCells: () => stateRef.current.cells.map((c) => c.source),
      navigate: navigateToCell,
      workspaceId,
      notebookPath: path,
    });
    return () => setLspDoc(null);
  }, [active, cellIds, workspaceId, path, navigateToCell]);

  // ── assistente de IA ──────────────────────────────────────────────────────
  const aiCtx = useCallback(
    (cellId?: string, selection?: string) => {
      const cells = stateRef.current.cells;
      const idx = cellId ? cells.findIndex((c) => c.id === cellId) : -1;
      const err = cellId ? useAssistantStore.getState().lastErrorByCell[cellId] : undefined;
      return {
        cells: cells.map((c) => c.source),
        active_cell_index: idx >= 0 ? idx : 0,
        notebook_path: path,
        session_id: null,
        selection: selection ?? null,
        recent_error: err ?? null,
      };
    },
    [path],
  );

  useEffect(() => {
    if (!active) return;
    setNotebookAiContext({
      forCell: (cellId, opts) => aiCtx(cellId, opts?.selection),
      overview: () => aiCtx(focusedCell ?? undefined),
    });
    return () => setNotebookAiContext(null);
  }, [active, aiCtx, focusedCell]);

  const runAi = useCallback(
    async (d: AiCommandDetail) => {
      const cell = stateRef.current.cells.find((c) => c.id === d.cellId);
      if (!cell) return;
      const store = useAssistantStore.getState();
      store.setResult(d.cellId, {
        task: d.task,
        text: "",
        streaming: true,
        error: null,
        originalSource: cell.source,
      });
      await assistantStream(
        {
          task: d.task,
          context: aiCtx(d.cellId),
          instruction: d.instruction ?? null,
          target_language: d.targetLanguage ?? null,
          cell_id: d.cellId,
        },
        {
          onDelta: (t) => useAssistantStore.getState().appendDelta(d.cellId, t),
          onDone: ({ error }) => useAssistantStore.getState().finishResult(d.cellId, error),
        },
      );
    },
    [aiCtx],
  );

  useEffect(() => {
    if (!active) return;
    const onCmd = (e: Event) => void runAi((e as CustomEvent<AiCommandDetail>).detail);
    window.addEventListener("nbp:ai-command", onCmd as EventListener);
    return () => window.removeEventListener("nbp:ai-command", onCmd as EventListener);
  }, [active, runAi]);

  // contexto de arquivos do Workspace p/ completion de caminhos em strings
  useEffect(() => {
    if (!active) return;
    setWorkspaceFsContext({
      listRelPaths: () => {
        const files: string[] = [];
        const walk = (n: FileNode): void => {
          for (const c of n.children ?? []) {
            if (c.type === "dir") walk(c);
            else files.push(c.path);
          }
        };
        if (tree.data) walk(tree.data);
        return files.map((rel) => relativeFrom(path, rel));
      },
    });
    return () => setWorkspaceFsContext(null);
  }, [active, tree.data, path]);

  // diagnósticos (debounce 500ms)
  const cellsKey = state.cells.map((c) => c.source).join(" ");
  useEffect(() => {
    if (!active || !diagnosticsEnabled) {
      setDiags([]);
      return;
    }
    const h = setTimeout(() => {
      void lspDiagnostics(
        stateRef.current.cells.map((c) => c.source),
        { workspaceId, notebookPath: path },
      ).then((r) => {
        if (r.ok) setDiags(r.items);
      });
    }, 500);
    return () => clearTimeout(h);
  }, [active, cellsKey, diagnosticsEnabled, workspaceId, path]);

  const diagByCell = useMemo(() => {
    const m = new Map<number, LspDiagnostic[]>();
    for (const d of diags) {
      const arr = m.get(d.cell_index) ?? [];
      arr.push(d);
      m.set(d.cell_index, arr);
    }
    return m;
  }, [diags]);

  const problems = useMemo(
    () => ({
      errors: diags.filter((d) => d.severity === "error").length,
      warnings: diags.filter((d) => d.severity === "warning").length,
    }),
    [diags],
  );

  // ── salvar ────────────────────────────────────────────────────────────────
  const save = useCallback(async () => {
    if (!stateRef.current.loaded) return;
    const content = toContent(stateRef.current);
    setSaveState("saving");
    try {
      const res = await write.mutateAsync({
        path,
        notebook: content as unknown as Record<string, unknown>,
        ifMatch: etagRef.current,
      });
      etagRef.current = res.etag ?? null;
      savedJson.current = JSON.stringify(content);
      setSaveState("saved");
      onDirtyChange(path, false);
    } catch (err) {
      setSaveState("error");
      toast.error(`Falha ao salvar: ${(err as Error).message}`);
    }
  }, [path, write, toast, onDirtyChange]);

  useAutosave({
    dirty,
    enabled: autosave.enabled,
    intervalMs: autosave.intervalMs,
    onSave: save,
  });

  // ── executar ──────────────────────────────────────────────────────────────
  const runCell = useCallback(
    async (id: string) => {
      const cell = stateRef.current.cells.find((c) => c.id === id);
      if (!cell || cell.cell_type !== "code") return "ok" as const;
      dispatch({ type: "runStart", id });
      return kernel.runCell(id, cell.source);
    },
    [kernel],
  );

  const cancelRequested = useRef(false);

  const runAllCells = useCallback(async () => {
    cancelRequested.current = false;
    const codeCells = stateRef.current.cells.filter((c) => c.cell_type === "code");
    setRunAll({ done: 0, total: codeCells.length });
    setPanelTab("execution");
    for (let i = 0; i < codeCells.length; i++) {
      if (cancelRequested.current) break;
      const res = await runCell(codeCells[i]!.id);
      setRunAll({ done: i + 1, total: codeCells.length });
      if (res === "error" || cancelRequested.current) break;
    }
    setRunAll(null);
  }, [runCell, setPanelTab]);

  const cancelRun = useCallback(() => {
    cancelRequested.current = true;
    kernel.interrupt();
    // SIGINT (interrupt) só para a chamada Python corrente; se em ~5s o kernel não
    // voltar (célula travada numa chamada nativa), reinicia o processo para liberar
    // os recursos de fato.
    window.setTimeout(() => {
      if (cancelRequested.current && kernelStatusRef.current === "busy") kernel.restart();
    }, 5000);
  }, [kernel]);

  const focusOrFirst = useCallback(() => {
    const cells = stateRef.current.cells;
    return focusedCell && cells.some((c) => c.id === focusedCell)
      ? focusedCell
      : cells[0]?.id ?? null;
  }, [focusedCell]);

  const runFocused = useCallback(
    (advance: "next" | "insert" | null) => {
      const id = focusOrFirst();
      if (!id) return;
      void runCell(id);
      const cells = stateRef.current.cells;
      const at = cells.findIndex((c) => c.id === id);
      if (advance === "next") {
        const next = cells[at + 1];
        if (next) setFocusedCell(next.id);
        else dispatch({ type: "add", afterId: id, cellType: "code" });
      } else if (advance === "insert") {
        dispatch({ type: "add", afterId: id, cellType: "code" });
      }
    },
    [focusOrFirst, runCell],
  );

  useHotkeys(
    {
      "mod+s": () => void save(),
      "mod+enter": () => runFocused(null),
      "shift+enter": () => runFocused("next"),
      "alt+enter": () => runFocused("insert"),
      "mod+shift+enter": () => void runAllCells(),
    },
    active,
  );

  // comandos vindos da Command Palette / toolbar do Workspace
  useEffect(() => {
    if (!active) return;
    const onCmd = (e: Event): void => {
      const cmd = (e as CustomEvent<string>).detail;
      if (cmd === "run-all") void runAllCells();
      else if (cmd === "restart-kernel") kernel.restart();
      else if (cmd === "interrupt-kernel") kernel.interrupt();
      else if (cmd === "save") void save();
      else if (cmd === "clear-outputs") dispatch({ type: "clearOutputs" });
      else if (cmd === "create-workflow") setWfDialog(true);
    };
    window.addEventListener("nbp:workspace-command", onCmd as EventListener);
    return () =>
      window.removeEventListener("nbp:workspace-command", onCmd as EventListener);
  }, [active, runAllCells, kernel, save]);

  // filesystem mudou por fora (watcher): reagir se for ESTE notebook
  const [extGone, setExtGone] = useState(false);
  const dirtyRef = useRef(dirty);
  dirtyRef.current = dirty;
  useEffect(() => {
    const onFs = (e: Event): void => {
      const d = (e as CustomEvent<{ op: string; path: string }>).detail;
      if (!d || d.path !== path) return;
      if (d.op === "deleted") setExtGone(true);
      else if (d.op === "updated" && !dirtyRef.current) void file.refetch();
    };
    window.addEventListener("nbp:fs-change", onFs as EventListener);
    return () => window.removeEventListener("nbp:fs-change", onFs as EventListener);
  }, [path, file]);

  // ── render ────────────────────────────────────────────────────────────────
  if (extGone) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center">
        <p className="text-sm text-danger">
          Este notebook foi removido de <span className="font-mono">/root</span> por
          outra ação. Não é possível salvar sobre um arquivo inexistente.
        </p>
        <Button
          size="sm"
          onClick={() => {
            setExtGone(false);
            void file.refetch();
          }}
        >
          Tentar recarregar
        </Button>
      </div>
    );
  }
  if (file.isLoading) {
    return (
      <div className="flex h-full items-center justify-center text-fg-faint">
        <SpinnerIcon className="h-5 w-5 animate-spin" />
      </div>
    );
  }
  if (file.isError || !file.data) {
    return (
      <div className="p-6 text-sm text-danger">
        Falha ao abrir o notebook: {(file.error as Error)?.message}
      </div>
    );
  }

  const kBusy = kernel.status === "busy" || runAll != null;
  const saveLabel =
    saveState === "saving"
      ? "Salvando…"
      : saveState === "error"
        ? "Falha ao salvar"
        : saveState === "dirty"
          ? "Não salvo"
          : "Salvo";

  return (
    <div className="flex h-full flex-col">
      {/* toolbar sticky */}
      <div className="sticky top-0 z-10 flex flex-wrap items-center gap-1.5 border-b border-surface-border bg-surface px-2 py-1.5">
        <Button
          size="sm"
          variant="text"
          icon={<AddIcon className="h-4 w-4" />}
          onClick={() =>
            dispatch({ type: "add", afterId: focusedCell, cellType: "code" })
          }
        >
          Code
        </Button>
        <Button
          size="sm"
          variant="text"
          icon={<AddIcon className="h-4 w-4" />}
          onClick={() =>
            dispatch({ type: "add", afterId: focusedCell, cellType: "markdown" })
          }
        >
          Markdown
        </Button>
        <span className="mx-1 h-4 w-px bg-surface-border" />
        {kBusy ? (
          <Button
            size="sm"
            variant="danger"
            icon={
              runAll ? (
                <SpinnerIcon className="h-4 w-4 animate-spin" />
              ) : (
                <StopIcon className="h-4 w-4" />
              )
            }
            onClick={cancelRun}
          >
            {runAll ? `Cancelar Execução (${runAll.done}/${runAll.total})` : "Cancelar Execução"}
          </Button>
        ) : (
          <Button
            size="sm"
            icon={<RunIcon className="h-4 w-4" />}
            onClick={() => void runAllCells()}
          >
            Executar tudo
          </Button>
        )}
        <Button
          size="sm"
          variant="text"
          icon={<RetryIcon className="h-4 w-4" />}
          onClick={kernel.restart}
        >
          Reiniciar
        </Button>
        <Button
          size="sm"
          variant="text"
          onClick={() => dispatch({ type: "clearOutputs" })}
        >
          Limpar saídas
        </Button>
        <Button size="sm" variant="text" onClick={() => setWfDialog(true)}>
          Criar Workflow
        </Button>

        <span className="ml-auto flex items-center gap-2 text-xs text-fg-muted">
          <button
            type="button"
            className="rounded px-1.5 py-0.5 hover:bg-surface-variant"
            title="Exportar .py"
            onClick={() =>
              void downloadExport(workspaceId, path, "py").catch((e) =>
                toast.error((e as Error).message),
              )
            }
          >
            <DownloadIcon className="inline h-3.5 w-3.5" /> .py
          </button>
          <span
            className={`flex items-center gap-1 ${
              kernel.status === "dead"
                ? "text-danger"
                : kernel.status === "idle"
                  ? "text-ok"
                  : "text-fg-muted"
            }`}
          >
            ● Python {KERNEL_LABEL[kernel.status] ?? kernel.status}
          </span>
          <Button
            size="sm"
            icon={<SaveIcon className="h-4 w-4" />}
            variant={saveState === "dirty" || saveState === "error" ? "filled" : "outlined"}
            loading={saveState === "saving"}
            onClick={() => void save()}
          >
            {saveLabel}
          </Button>
        </span>
      </div>

      {kernel.status === "dead" && (
        <div className="flex items-center gap-2 bg-danger/10 px-3 py-1.5 text-xs text-danger">
          O kernel parou.
          <button
            type="button"
            className="rounded bg-danger/20 px-2 py-0.5 font-medium"
            onClick={kernel.restart}
          >
            Reiniciar kernel
          </button>
        </div>
      )}

      <div className="min-h-0 flex-1 space-y-3 overflow-auto p-3">
        {state.cells.map((cell, i) => (
          <WorkspaceCell
            key={cell.id}
            cell={cell}
            index={i}
            total={state.cells.length}
            theme={theme}
            modelPath={
              cell.cell_type === "code"
                ? wsCellModelPath(workspaceId, path, cell.id)
                : `file:///wsnb-md/${workspaceId}/${cell.id}.md`
            }
            diagnostics={diagByCell.get(i)}
            getCells={() => stateRef.current.cells.map((c) => c.source)}
            lspCtx={lspCtx}
            onSource={(id, src) => dispatch({ type: "setSource", id, source: src })}
            onType={(id, t) => dispatch({ type: "setType", id, cellType: t })}
            onRun={(id) => void runCell(id)}
            onInterrupt={kernel.interrupt}
            onMove={(id, dir) => dispatch({ type: "move", id, dir })}
            onDuplicate={(id) => dispatch({ type: "duplicate", id })}
            onRemove={(id) => dispatch({ type: "remove", id })}
            onAddBelow={(id) => dispatch({ type: "add", afterId: id, cellType: "code" })}
            onFocusCell={setFocusedCell}
            onRegisterEditor={registerEditor}
            onNavigate={navigateToCell}
            onShowLocations={(title, locations) => setLocPanel({ title, locations })}
            onAiInsert={(id, code) => {
              const c = stateRef.current.cells.find((x) => x.id === id);
              dispatch({ type: "setSource", id, source: (c?.source ?? "") + code });
            }}
            onAiInsertBelow={(id, code) => {
              dispatch({ type: "add", afterId: id, cellType: "code" });
              // a nova célula é a próxima; preenche no próximo tick
              setTimeout(() => {
                const cells = stateRef.current.cells;
                const at = cells.findIndex((x) => x.id === id);
                const next = cells[at + 1];
                if (next) dispatch({ type: "setSource", id: next.id, source: code });
              }, 0);
            }}
            onAiReplace={(id, code) => dispatch({ type: "setSource", id, source: code })}
          />
        ))}
        {state.cells.length === 0 && (
          <button
            type="button"
            className="w-full rounded border border-dashed border-surface-border py-6 text-sm text-fg-faint hover:bg-surface-variant"
            onClick={() => dispatch({ type: "add", afterId: null, cellType: "code" })}
          >
            + Adicionar célula
          </button>
        )}

        {(problems.errors > 0 || problems.warnings > 0) && (
          <button
            type="button"
            onClick={() => setShowProblems((v) => !v)}
            className="text-xs text-fg-muted hover:text-fg"
          >
            {problems.errors} erro(s) · {problems.warnings} aviso(s)
          </button>
        )}
        {showProblems && (
          <ProblemsPanel
            diagnostics={diags}
            onSelect={navigateToCell}
            onClose={() => setShowProblems(false)}
          />
        )}
        {locPanel && (
          <LocationsPanel
            title={locPanel.title}
            locations={locPanel.locations}
            onSelect={navigateToCell}
            onClose={() => setLocPanel(null)}
          />
        )}
      </div>

      <CreateWorkflowDialog
        open={wfDialog}
        notebookPath={path}
        onClose={() => setWfDialog(false)}
        onCreated={(wid) => navigate(`/workflows/${wid}`)}
      />
    </div>
  );
}
