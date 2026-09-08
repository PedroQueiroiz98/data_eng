import { useEffect, useMemo, useRef, useState } from "react";
import Editor, { type OnMount } from "@monaco-editor/react";
import * as monacoNS from "monaco-editor";
import DOMPurify from "dompurify";
import { marked } from "marked";
import { CellOutputList } from "@/components/notebook/mime/CellOutput";
import { getEditorConfig } from "@/lib/editorConfig";
import {
  lspDefinition,
  lspReferences,
  type LspDiagnostic,
  type LspLocation,
} from "@/lib/lsp";
import type { RunStatus, WCell } from "@/store/workspaceNotebook";
import {
  AddIcon,
  DeleteIcon,
  DuplicateIcon,
  RunIcon,
  SpinnerIcon,
  StopIcon,
} from "@/ui/icons";

interface Props {
  cell: WCell;
  index: number;
  total: number;
  theme: "light" | "dark";
  modelPath: string;
  diagnostics?: LspDiagnostic[];
  getCells: () => string[];
  lspCtx: () => { workspaceId: string; notebookPath: string };
  onSource: (id: string, src: string) => void;
  onType: (id: string, t: WCell["cell_type"]) => void;
  onRun: (id: string) => void;
  onInterrupt: () => void;
  onMove: (id: string, dir: "up" | "down") => void;
  onDuplicate: (id: string) => void;
  onRemove: (id: string) => void;
  onAddBelow: (id: string) => void;
  onFocusCell: (id: string) => void;
  onRegisterEditor: (
    index: number,
    editor: monacoNS.editor.IStandaloneCodeEditor | null,
  ) => void;
  onNavigate: (cellIndex: number, line: number, column: number) => void;
  onShowLocations: (title: string, locations: LspLocation[]) => void;
}

const STATUS_DOT: Record<RunStatus, string> = {
  idle: "text-fg-faint",
  running: "text-info",
  ok: "text-ok",
  error: "text-danger",
  cancelled: "text-warn",
};

const SEV: Record<string, monacoNS.MarkerSeverity> = {
  error: monacoNS.MarkerSeverity.Error,
  warning: monacoNS.MarkerSeverity.Warning,
  information: monacoNS.MarkerSeverity.Info,
  hint: monacoNS.MarkerSeverity.Hint,
};

export function WorkspaceCell({
  cell,
  index,
  total,
  theme,
  modelPath,
  diagnostics,
  getCells,
  lspCtx,
  onSource,
  onType,
  onRun,
  onInterrupt,
  onMove,
  onDuplicate,
  onRemove,
  onAddBelow,
  onFocusCell,
  onRegisterEditor,
  onNavigate,
  onShowLocations,
}: Props) {
  const isCode = cell.cell_type === "code";
  const [mdEditing, setMdEditing] = useState(cell.source.trim() === "");
  const editorRef = useRef<monacoNS.editor.IStandaloneCodeEditor | null>(null);
  const lines = cell.source.split("\n").length;
  const height = Math.min(460, Math.max(64, lines * 19 + 16));

  const mdHtml = useMemo(() => {
    if (cell.cell_type !== "markdown") return "";
    return DOMPurify.sanitize(
      marked.parse(cell.source || "*vazio*", { async: false }) as string,
    );
  }, [cell.cell_type, cell.source]);

  const running = cell.runStatus === "running";
  const count =
    cell.execution_count != null ? `[${cell.execution_count}]` : running ? "[*]" : "[ ]";

  const handleMount: OnMount = (editor, monaco) => {
    editorRef.current = editor;
    onRegisterEditor(index, editor);
    const ctx = () => lspCtx();
    editor.addAction({
      id: "nbp.ws.goToDefinition",
      label: "Ir para definição (notebook)",
      keybindings: [monaco.KeyMod.CtrlCmd | monaco.KeyCode.F12, monaco.KeyCode.F12],
      contextMenuGroupId: "navigation",
      contextMenuOrder: 1.1,
      async run(ed) {
        const pos = ed.getPosition();
        if (!pos) return;
        const res = await lspDefinition({
          cells: getCells(),
          cellIndex: index,
          line: pos.lineNumber - 1,
          column: pos.column - 1,
          ...ctx(),
        });
        if (!res.ok || res.locations.length === 0) return;
        const local = res.locations.find((l) => !l.external && l.cell_index >= 0);
        if (local) onNavigate(local.cell_index, local.line, local.column);
        else onShowLocations("Definição (biblioteca externa)", res.locations);
      },
    });
    editor.addAction({
      id: "nbp.ws.findReferences",
      label: "Localizar referências (notebook)",
      keybindings: [monaco.KeyMod.Shift | monaco.KeyCode.F12],
      contextMenuGroupId: "navigation",
      contextMenuOrder: 1.2,
      async run(ed) {
        const pos = ed.getPosition();
        if (!pos) return;
        const res = await lspReferences({
          cells: getCells(),
          cellIndex: index,
          line: pos.lineNumber - 1,
          column: pos.column - 1,
          ...ctx(),
        });
        if (res.ok) onShowLocations(`Referências (${res.locations.length})`, res.locations);
      },
    });
  };

  useEffect(() => {
    const model = editorRef.current?.getModel();
    if (!model) return;
    monacoNS.editor.setModelMarkers(
      model,
      "nbp-lsp",
      (diagnostics ?? []).map((d) => ({
        severity: SEV[d.severity] ?? monacoNS.MarkerSeverity.Info,
        message: `${d.message}${d.code ? ` (${d.code})` : ""}`,
        source: d.source,
        startLineNumber: d.line + 1,
        startColumn: d.column + 1,
        endLineNumber: d.line + 1,
        endColumn: (d.end_column ?? d.column + 1) + 1,
      })),
    );
  }, [diagnostics]);

  useEffect(
    () => () => onRegisterEditor(index, null),
    [index, onRegisterEditor],
  );

  return (
    <div
      className={`rounded border bg-surface ${
        running ? "border-info/50" : cell.runStatus === "error" ? "border-danger/50" : "border-surface-border"
      }`}
      onClick={() => onFocusCell(cell.id)}
    >
      <div className="flex items-center gap-2 border-b border-surface-border px-2 py-1 text-xs">
        {isCode ? (
          <button
            type="button"
            title={running ? "Interromper" : "Executar (Ctrl+Enter)"}
            className="rounded p-0.5 text-primary hover:bg-surface-variant"
            onClick={(e) => {
              e.stopPropagation();
              running ? onInterrupt() : onRun(cell.id);
            }}
          >
            {running ? <StopIcon className="h-4 w-4" /> : <RunIcon className="h-4 w-4" />}
          </button>
        ) : (
          <span className="w-5" />
        )}
        <span className="w-8 text-fg-faint">{count}</span>
        <select
          value={cell.cell_type}
          onChange={(e) => onType(cell.id, e.target.value as WCell["cell_type"])}
          onClick={(e) => e.stopPropagation()}
          className="rounded border border-surface-border bg-surface px-1 py-0.5"
        >
          <option value="code">code</option>
          <option value="markdown">markdown</option>
          <option value="raw">raw</option>
        </select>
        {cell.metadata.tags != null &&
          Array.isArray(cell.metadata.tags) &&
          (cell.metadata.tags as string[]).includes("parameters") && (
            <span className="rounded bg-warn/15 px-1.5 py-0.5 text-warn">parameters</span>
          )}
        <span className={`flex items-center gap-1 ${STATUS_DOT[cell.runStatus]}`}>
          {running ? (
            <SpinnerIcon className="h-3 w-3 animate-spin" />
          ) : (
            <span className="text-[10px]">●</span>
          )}
          {cell.durationMs != null && !running
            ? `${(cell.durationMs / 1000).toFixed(2)}s`
            : ""}
        </span>
        <div className="ml-auto flex items-center gap-0.5" onClick={(e) => e.stopPropagation()}>
          <button type="button" className="btn-cell" disabled={index === 0} onClick={() => onMove(cell.id, "up")} title="Mover para cima">↑</button>
          <button type="button" className="btn-cell" disabled={index === total - 1} onClick={() => onMove(cell.id, "down")} title="Mover para baixo">↓</button>
          <button type="button" className="btn-cell" onClick={() => onDuplicate(cell.id)} title="Duplicar">
            <DuplicateIcon className="h-3.5 w-3.5" />
          </button>
          <button type="button" className="btn-cell" onClick={() => onAddBelow(cell.id)} title="Adicionar abaixo">
            <AddIcon className="h-3.5 w-3.5" />
          </button>
          <button type="button" className="btn-cell text-danger" disabled={total === 1} onClick={() => onRemove(cell.id)} title="Remover">
            <DeleteIcon className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      {cell.cell_type === "markdown" && !mdEditing ? (
        <div
          className="nbp-html-output prose-sm max-w-none px-4 py-2 text-sm"
          onDoubleClick={() => setMdEditing(true)}
          dangerouslySetInnerHTML={{ __html: mdHtml }}
        />
      ) : (
        <Editor
          height={height}
          path={modelPath}
          theme={theme === "dark" ? "vs-dark" : "vs"}
          language={isCode ? "python" : cell.cell_type === "markdown" ? "markdown" : "plaintext"}
          value={cell.source}
          onChange={(v) => onSource(cell.id, v ?? "")}
          onMount={handleMount}
          options={{
            minimap: { enabled: false },
            lineNumbers: isCode ? "on" : "off",
            scrollBeyondLastLine: false,
            fontSize: 13,
            automaticLayout: true,
            padding: { top: 8, bottom: 8 },
            quickSuggestions: getEditorConfig().editor.autocomplete,
            suggestOnTriggerCharacters: getEditorConfig().editor.autocomplete,
            parameterHints: { enabled: getEditorConfig().editor.signatureHelp },
            hover: { enabled: getEditorConfig().editor.hover },
            wordWrap: isCode ? "off" : "on",
          }}
        />
      )}

      {cell.cell_type === "markdown" && mdEditing && (
        <div className="border-t border-surface-border px-2 py-1 text-right">
          <button
            type="button"
            className="rounded px-2 py-0.5 text-xs text-primary hover:bg-surface-variant"
            onClick={() => setMdEditing(false)}
          >
            Concluir
          </button>
        </div>
      )}

      {isCode && <CellOutputList outputs={cell.outputs} />}
    </div>
  );
}
