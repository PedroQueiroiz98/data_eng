import { Handle, Position, type NodeProps } from "@xyflow/react";

export interface TaskNodeData {
  name: string;
  /** rótulo exibido (basename do notebook do Workspace, ou nome legado) */
  notebookName: string | null;
  /** legado — notebook do módulo global */
  notebookId: string | null;
  /** notebook = arquivo do Workspace */
  workspaceId: string | null;
  notebookPath: string | null;
  timeoutS: number | null;
  maxRetries: number;
  [key: string]: unknown;
}

export function TaskNode({ data, selected }: NodeProps) {
  const d = data as TaskNodeData;
  return (
    <div
      className={`min-w-40 rounded border bg-surface px-3 py-2 shadow-sm ${
        selected ? "border-primary" : "border-surface-border"
      }`}
    >
      <Handle type="target" position={Position.Top} />
      <div className="text-sm font-medium text-fg">{d.name || "—"}</div>
      <div className="mt-0.5 text-xs text-fg-muted">
        {d.notebookName ? `📓 ${d.notebookName}` : "sem notebook"}
      </div>
      {(d.maxRetries > 0 || d.timeoutS) && (
        <div className="mt-1 text-[10px] text-fg-faint">
          {d.timeoutS ? `timeout ${d.timeoutS}s` : ""}
          {d.timeoutS && d.maxRetries > 0 ? " · " : ""}
          {d.maxRetries > 0 ? `retries ${d.maxRetries}` : ""}
        </div>
      )}
      <Handle type="source" position={Position.Bottom} />
    </div>
  );
}
