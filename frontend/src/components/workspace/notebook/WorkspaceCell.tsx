import { useEffect, useMemo, useRef, useState } from "react";
import Editor, { type OnMount } from "@monaco-editor/react";
import * as monacoNS from "monaco-editor";
import DOMPurify from "dompurify";
import { marked } from "marked";
import { CellOutputList } from "@/components/notebook/mime/CellOutput";
import { AiCellMenu } from "@/components/assistant/AiCellMenu";
import { AiInlineWidget } from "@/components/assistant/AiInlineWidget";
import { AiResultCard } from "@/components/assistant/AiResultCard";
import { getEditorConfig } from "@/lib/editorConfig";
import {
  lspDefinition,
  lspReferences,
  type LspDiagnostic,
  type LspLocation,
} from "@/lib/lsp";
import { getAssistantState, useAssistantStore } from "@/store/assistant";
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
  onAiInsert: (id: string, code: string) => void;
  onAiInsertBelow: (id: string, code: string) => void;
  onAiReplace: (id: string, code: string) => void;
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
  onAiInsert,
  onAiInsertBelow,
  onAiReplace,
}: Props) {
  const isCode = cell.cell_type === "code";
  const aiResult = useAssistantStore((s) => s.resultByCell[cell.id]);
  const setAiResult = useAssistantStore((s) => s.setResult);
  const aiAvailable =
    useAssistantStore((s) => s.available) && getEditorConfig().ai.enabled;
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
      id: "nbp.ai.ask",
      label: "Perguntar à IA (Ctrl+K)",
      keybindings: [monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyK],
      contextMenuGroupId: "1_ai",
      contextMenuOrder: 0.1,
      run() {
        if (getEditorConfig().ai.enabled && getAssistantState().available) {
          getAssistantState().openAsk(cell.id);
        }
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
          {isCode && <AiCellMenu cellId={cell.id} />}
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

      {isCode && <AiInlineWidget cellId={cell.id} />}

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
            inlineSuggest: { enabled: getEditorConfig().editor.inlineSuggestions },
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

      {isCode && cell.runStatus === "error" && !aiResult && aiAvailable && (
        <div className="flex items-center gap-2 border-t border-danger/20 bg-danger/5 px-3 py-1.5 text-xs text-danger">
          ⚠️ Erro de execução
          <button
            type="button"
            className="rounded bg-danger/15 px-2 py-0.5 font-medium hover:bg-danger/25"
            onClick={() =>
              window.dispatchEvent(
                new CustomEvent("nbp:ai-command", {
                  detail: { task: "FIX", cellId: cell.id },
                }),
              )
            }
          >
            Corrigir com IA
          </button>
        </div>
      )}

      {aiResult && (
        <div className="px-3 pb-2">
          <AiResultCard
            task={aiResult.task}
            text={aiResult.text}
            streaming={aiResult.streaming}
            error={aiResult.error}
            originalSource={aiResult.originalSource}
            onInsert={(code) => {
              onAiInsert(cell.id, code);
              setAiResult(cell.id, null);
            }}
            onInsertBelow={(code) => {
              onAiInsertBelow(cell.id, code);
              setAiResult(cell.id, null);
            }}
            onReplace={(code) => {
              onAiReplace(cell.id, code);
              setAiResult(cell.id, null);
            }}
            onReject={() => setAiResult(cell.id, null)}
          />
        </div>
      )}
    </div>
  );
}
