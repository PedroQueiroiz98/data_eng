import { Handle, Position, type NodeProps } from "@xyflow/react";

export interface TaskNodeData {
  name: string;
  notebookName: string | null;
  notebookId: string | null;
  timeoutS: number | null;
  maxRetries: number;
  [key: string]: unknown;
}

export function TaskNode({ data, selected }: NodeProps) {
  const d = data as TaskNodeData;
  return (
    <div
      className={`min-w-40 rounded border bg-white px-3 py-2 shadow-sm ${
        selected ? "border-slate-500" : "border-slate-300"
      }`}
    >
      <Handle type="target" position={Position.Top} />
      <div className="text-sm font-medium text-slate-800">{d.name || "—"}</div>
      <div className="mt-0.5 text-xs text-slate-500">
        {d.notebookName ? `📓 ${d.notebookName}` : "sem notebook"}
      </div>
      {(d.maxRetries > 0 || d.timeoutS) && (
        <div className="mt-1 text-[10px] text-slate-400">
          {d.timeoutS ? `timeout ${d.timeoutS}s` : ""}
          {d.timeoutS && d.maxRetries > 0 ? " · " : ""}
          {d.maxRetries > 0 ? `retries ${d.maxRetries}` : ""}
        </div>
      )}
      <Handle type="source" position={Position.Bottom} />
    </div>
  );
}
