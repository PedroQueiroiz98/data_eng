import type { ReactNode } from "react";
import { fmtDuration, type JobStatus, type JobTask, type TaskCounts, taskCounts } from "@/lib/jobs";
import { StatusIcon } from "@/ui";

interface Props {
  status: JobStatus;
  durationMs: number | null;
  startedAt: string | null;
  finishedAt: string | null;
  trigger: string;
  startedBy: string | null;
  tasks: JobTask[];
  elapsedLabel?: string; // para RUNNING: "01:42"
}

function Stat({ label, value, tone }: { label: string; value: ReactNode; tone?: string }) {
  return (
    <div>
      <div className="text-[11px] font-medium uppercase tracking-wide text-fg-faint">{label}</div>
      <div className={`mt-0.5 text-sm tabular-nums ${tone ?? "text-fg"}`}>{value}</div>
    </div>
  );
}

export function JobSummary({
  status,
  durationMs,
  startedAt,
  finishedAt,
  trigger,
  startedBy,
  tasks,
  elapsedLabel,
}: Props) {
  const c: TaskCounts = taskCounts(tasks);
  return (
    <div className="surface p-4">
      <div className="flex flex-wrap items-center gap-3">
        <StatusIcon status={status} className="h-6 w-6" />
        <span className="text-lg font-semibold text-fg">{status}</span>
        {status === "RUNNING" && elapsedLabel && (
          <span className="rounded bg-info/15 px-2 py-0.5 font-mono text-xs text-info">
            {elapsedLabel}
          </span>
        )}
      </div>

      <div className="mt-3 grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-3 lg:grid-cols-4">
        <Stat label="Duração" value={fmtDuration(durationMs)} />
        <Stat label="Jobs" value={c.total} />
        <Stat label="Success" value={c.success} tone="text-ok" />
        <Stat
          label="Failed"
          value={c.failed}
          tone={c.failed ? "text-danger" : "text-fg"}
        />
        <Stat label="Skipped" value={c.skipped} tone={c.skipped ? "text-warn" : "text-fg"} />
        <Stat label="Trigger" value={trigger.toLowerCase()} />
        <Stat label="Iniciado por" value={startedBy ?? "—"} />
        <Stat
          label="Início"
          value={startedAt ? new Date(startedAt).toLocaleTimeString() : "—"}
        />
        <Stat
          label="Término"
          value={finishedAt ? new Date(finishedAt).toLocaleTimeString() : "—"}
        />
      </div>
    </div>
  );
}
