import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from "react";
import { useTheme } from "@/components/ThemeProvider";
import { WorkspaceCell } from "@/components/workspace/notebook/WorkspaceCell";
import { useAutosave } from "@/hooks/useAutosave";
import { useHotkeys } from "@/hooks/useHotkeys";
import { useKernel } from "@/hooks/useKernel";
import { useWorkspaceFile, useWriteFile } from "@/hooks/useWorkspace";
import type { KernelEvent } from "@/lib/kernels";
import type { NotebookContent } from "@/lib/notebooks";
import { downloadExport } from "@/lib/workspaceData";
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
  const file = useWorkspaceFile(workspaceId, path);
  const write = useWriteFile(workspaceId);
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
    } else if ((e.type === "cell.output" || e.type === "cell.error") && e.output) {
      dispatch({ type: "cellOutput", id: e.cell_id, output: e.output });
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

  useEffect(() => {
    if (active) {
      useWorkspaceRuntime.getState().setKernel(kernel.status, kernel.connected);
    }
  }, [active, kernel.status, kernel.connected]);

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

  const runAllCells = useCallback(async () => {
    const codeCells = stateRef.current.cells.filter((c) => c.cell_type === "code");
    setRunAll({ done: 0, total: codeCells.length });
    setPanelTab("execution");
    for (let i = 0; i < codeCells.length; i++) {
      const res = await runCell(codeCells[i]!.id);
      setRunAll({ done: i + 1, total: codeCells.length });
      if (res === "error") break;
    }
    setRunAll(null);
  }, [runCell, setPanelTab]);

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
    };
    window.addEventListener("nbp:workspace-command", onCmd as EventListener);
    return () =>
      window.removeEventListener("nbp:workspace-command", onCmd as EventListener);
  }, [active, runAllCells, kernel, save]);

  // ── render ────────────────────────────────────────────────────────────────
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
        <Button
          size="sm"
          icon={
            runAll ? (
              <SpinnerIcon className="h-4 w-4 animate-spin" />
            ) : (
              <RunIcon className="h-4 w-4" />
            )
          }
          disabled={kBusy && !runAll}
          onClick={() => void runAllCells()}
        >
          {runAll ? `Executando ${runAll.done}/${runAll.total}` : "Executar tudo"}
        </Button>
        <Button
          size="sm"
          variant="text"
          icon={<StopIcon className="h-4 w-4" />}
          disabled={kernel.status !== "busy"}
          onClick={kernel.interrupt}
        >
          Interromper
        </Button>
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
            modelPath={`wsnb:${workspaceId}:${path}:${cell.id}.${
              cell.cell_type === "code" ? "py" : "md"
            }`}
            onSource={(id, src) => dispatch({ type: "setSource", id, source: src })}
            onType={(id, t) => dispatch({ type: "setType", id, cellType: t })}
            onRun={(id) => void runCell(id)}
            onInterrupt={kernel.interrupt}
            onMove={(id, dir) => dispatch({ type: "move", id, dir })}
            onDuplicate={(id) => dispatch({ type: "duplicate", id })}
            onRemove={(id) => dispatch({ type: "remove", id })}
            onAddBelow={(id) => dispatch({ type: "add", afterId: id, cellType: "code" })}
            onFocusCell={setFocusedCell}
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
      </div>
    </div>
  );
}
