import { CellOutputs } from "@/components/notebook/CellOutputs";
import { cellText, type NotebookCell, type NotebookContent } from "@/lib/notebooks";

export function NotebookOutputView({ notebook }: { notebook: NotebookContent }) {
  return (
    <div className="space-y-3">
      {notebook.cells.map((cell: NotebookCell, i) => (
        <div key={cell.id ?? i} className="rounded border border-slate-200 bg-white">
          <div className="border-b border-slate-100 px-2 py-1 text-xs text-slate-400">
            [{i + 1}] {cell.cell_type}
            {typeof cell.execution_count === "number" && ` · exec ${cell.execution_count}`}
          </div>
          <pre className="overflow-x-auto whitespace-pre-wrap px-3 py-2 font-mono text-xs text-slate-800">
            {cellText(cell)}
          </pre>
          {cell.cell_type === "code" && <CellOutputs outputs={cell.outputs} />}
        </div>
      ))}
    </div>
  );
}
