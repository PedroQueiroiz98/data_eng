import type { ExecutionStatus } from "@/lib/executions";

const STYLES: Record<string, string> = {
  QUEUED: "bg-slate-100 text-slate-600",
  RUNNING: "bg-blue-100 text-blue-700",
  SUCCESS: "bg-green-100 text-green-700",
  FAILED: "bg-red-100 text-red-700",
  CANCELLED: "bg-slate-200 text-slate-600",
  TIMEOUT: "bg-amber-100 text-amber-800",
};

const ICON: Record<string, string> = {
  QUEUED: "○",
  RUNNING: "◐",
  SUCCESS: "✓",
  FAILED: "✕",
  CANCELLED: "⊘",
  TIMEOUT: "⏱",
};

export function StatusBadge({ status }: { status: ExecutionStatus | string }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded px-2 py-0.5 text-xs font-medium ${
        STYLES[status] ?? "bg-slate-100 text-slate-600"
      }`}
    >
      <span aria-hidden>{ICON[status] ?? "•"}</span>
      {status}
    </span>
  );
}
