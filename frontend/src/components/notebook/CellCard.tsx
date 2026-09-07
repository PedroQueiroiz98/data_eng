import { useEffect, useRef } from "react";
import Editor, { type OnMount } from "@monaco-editor/react";
import * as monacoNS from "monaco-editor";
import { useTheme } from "@/components/ThemeProvider";
import { CellOutputs } from "@/components/notebook/CellOutputs";
import { getEditorConfig } from "@/lib/editorConfig";
import { lspDefinition, lspReferences, type LspDiagnostic, type LspLocation } from "@/lib/lsp";
import { cellModelPath } from "@/lib/lspShared";
import { useNotebookEditor, type EditorCell } from "@/store/notebookEditor";

interface Props {
  cell: EditorCell;
  index: number;
  total: number;
  notebookId: string;
  diagnostics?: LspDiagnostic[];
  onRegisterEditor?: (index: number, editor: monacoNS.editor.IStandaloneCodeEditor | null) => void;
  onNavigate?: (cellIndex: number, line: number, column: number) => void;
  onShowLocations?: (title: string, locations: LspLocation[]) => void;
}

const sourceString = (source: string | string[]): string =>
  Array.isArray(source) ? source.join("") : source;

const liveCells = (): string[] =>
  useNotebookEditor.getState().cells.map((c) => sourceString(c.source));

const SEV: Record<string, monacoNS.MarkerSeverity> = {
  error: monacoNS.MarkerSeverity.Error,
  warning: monacoNS.MarkerSeverity.Warning,
  information: monacoNS.MarkerSeverity.Info,
  hint: monacoNS.MarkerSeverity.Hint,
};

export function CellCard({
  cell,
  index,
  total,
  notebookId,
  diagnostics,
  onRegisterEditor,
  onNavigate,
  onShowLocations,
}: Props) {
  const { setSource, setCellType, addCell, removeCell, duplicateCell, moveCell, select, selectedId } =
    useNotebookEditor();
  const { theme } = useTheme();
  const editorRef = useRef<monacoNS.editor.IStandaloneCodeEditor | null>(null);

  const value = sourceString(cell.source);
  const lines = value.split("\n").length;
  const height = Math.min(420, Math.max(72, lines * 19 + 16));
  const isParams = cell.metadata.tags?.includes("parameters");
  const selected = selectedId === cell.localId;
  const isCode = cell.cell_type === "code";

  const handleMount: OnMount = (editor, monaco) => {
    editorRef.current = editor;
    onRegisterEditor?.(index, editor);

    editor.addAction({
      id: "nbp.goToDefinition",
      label: "Ir para definição (notebook)",
      keybindings: [monaco.KeyMod.CtrlCmd | monaco.KeyCode.F12, monaco.KeyCode.F12],
      contextMenuGroupId: "navigation",
      contextMenuOrder: 1.1,
      async run(ed) {
        const pos = ed.getPosition();
        if (!pos) return;
        const res = await lspDefinition({
          cells: liveCells(),
          cellIndex: index,
          line: pos.lineNumber - 1,
          column: pos.column - 1,
        });
        if (!res.ok || res.locations.length === 0) return;
        const local = res.locations.find((l) => !l.external && l.cell_index >= 0);
        if (local) onNavigate?.(local.cell_index, local.line, local.column);
        else onShowLocations?.("Definição (biblioteca externa)", res.locations);
      },
    });

    editor.addAction({
      id: "nbp.findReferences",
      label: "Localizar referências (notebook)",
      keybindings: [monaco.KeyMod.Shift | monaco.KeyCode.F12],
      contextMenuGroupId: "navigation",
      contextMenuOrder: 1.2,
      async run(ed) {
        const pos = ed.getPosition();
        if (!pos) return;
        const res = await lspReferences({
          cells: liveCells(),
          cellIndex: index,
          line: pos.lineNumber - 1,
          column: pos.column - 1,
        });
        if (res.ok) onShowLocations?.(`Referências (${res.locations.length})`, res.locations);
      },
    });
  };

  // marcadores de diagnóstico nesta célula
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
    () => () => {
      onRegisterEditor?.(index, null);
    },
    [index, onRegisterEditor],
  );

  return (
    <div
      className={`rounded border ${selected ? "border-primary" : "border-surface-border"} bg-surface`}
      onClick={() => select(cell.localId)}
    >
      <div className="flex items-center gap-2 border-b border-surface-border px-2 py-1 text-xs">
        <span className="w-10 text-fg-faint">[{index + 1}]</span>
        <select
          value={cell.cell_type}
          onChange={(e) => setCellType(cell.localId, e.target.value as EditorCell["cell_type"])}
          className="rounded border border-surface-border px-1 py-0.5"
        >
          <option value="code">code</option>
          <option value="markdown">markdown</option>
          <option value="raw">raw</option>
        </select>
        {isParams && (
          <span className="rounded bg-warn/15 px-1.5 py-0.5 text-warn">parameters</span>
        )}
        <div className="ml-auto flex items-center gap-1">
          <button type="button" className="btn-cell" disabled={index === 0}
            onClick={() => moveCell(cell.localId, "up")} title="Mover para cima">↑</button>
          <button type="button" className="btn-cell" disabled={index === total - 1}
            onClick={() => moveCell(cell.localId, "down")} title="Mover para baixo">↓</button>
          <button type="button" className="btn-cell" onClick={() => duplicateCell(cell.localId)}
            title="Duplicar">⧉</button>
          <button type="button" className="btn-cell" onClick={() => addCell("code", cell.localId)}
            title="Adicionar célula abaixo">+</button>
          <button type="button" className="btn-cell text-danger" disabled={total === 1}
            onClick={() => removeCell(cell.localId)} title="Remover">✕</button>
        </div>
      </div>

      <Editor
        height={height}
        path={isCode ? cellModelPath(notebookId, cell.localId) : undefined}
        theme={theme === "dark" ? "vs-dark" : "vs"}
        language={isCode ? "python" : cell.cell_type === "markdown" ? "markdown" : "plaintext"}
        value={value}
        onChange={(v) => setSource(cell.localId, v ?? "")}
        onMount={handleMount}
        options={{
          minimap: { enabled: false },
          lineNumbers: "on",
          scrollBeyondLastLine: false,
          fontSize: 13,
          automaticLayout: true,
          padding: { top: 8, bottom: 8 },
          quickSuggestions: getEditorConfig().editor.autocomplete,
          suggestOnTriggerCharacters: getEditorConfig().editor.autocomplete,
          parameterHints: { enabled: getEditorConfig().editor.signatureHelp },
          hover: { enabled: getEditorConfig().editor.hover },
        }}
      />

      {isCode && <CellOutputs outputs={cell.outputs} />}
    </div>
  );
}
