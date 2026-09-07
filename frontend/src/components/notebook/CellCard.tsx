import Editor from "@monaco-editor/react";
import { useTheme } from "@/components/ThemeProvider";
import { CellOutputs } from "@/components/notebook/CellOutputs";
import { useNotebookEditor, type EditorCell } from "@/store/notebookEditor";

interface Props {
  cell: EditorCell;
  index: number;
  total: number;
}

const sourceString = (source: string | string[]): string =>
  Array.isArray(source) ? source.join("") : source;

export function CellCard({ cell, index, total }: Props) {
  const { setSource, setCellType, addCell, removeCell, duplicateCell, moveCell, select, selectedId } =
    useNotebookEditor();
  const { theme } = useTheme();

  const value = sourceString(cell.source);
  const lines = value.split("\n").length;
  const height = Math.min(420, Math.max(72, lines * 19 + 16));
  const isParams = cell.metadata.tags?.includes("parameters");
  const selected = selectedId === cell.localId;

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
        theme={theme === "dark" ? "vs-dark" : "vs"}
        language={cell.cell_type === "code" ? "python" : cell.cell_type === "markdown" ? "markdown" : "plaintext"}
        value={value}
        onChange={(v) => setSource(cell.localId, v ?? "")}
        options={{
          minimap: { enabled: false },
          lineNumbers: "on",
          scrollBeyondLastLine: false,
          fontSize: 13,
          automaticLayout: true,
          padding: { top: 8, bottom: 8 },
        }}
      />

      {cell.cell_type === "code" && <CellOutputs outputs={cell.outputs} />}
    </div>
  );
}
