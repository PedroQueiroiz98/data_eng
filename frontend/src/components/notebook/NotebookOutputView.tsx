import { CellOutputs } from "@/components/notebook/CellOutputs";
import { cellText, type NotebookCell, type NotebookContent } from "@/lib/notebooks";

export function NotebookOutputView({ notebook }: { notebook: NotebookContent }) {
  return (
    <div className="space-y-3">
      {notebook.cells.map((cell: NotebookCell, i) => (
        <div key={cell.id ?? i} className="rounded border border-surface-border bg-surface">
          <div className="border-b border-surface-border px-2 py-1 text-xs text-fg-faint">
            [{i + 1}] {cell.cell_type}
            {typeof cell.execution_count === "number" && ` · exec ${cell.execution_count}`}
          </div>
          <pre className="overflow-x-auto whitespace-pre-wrap px-3 py-2 font-mono text-xs text-fg">
            {cellText(cell)}
          </pre>
          {cell.cell_type === "code" && <CellOutputs outputs={cell.outputs} />}
        </div>
      ))}
    </div>
  );
}
