import { useEffect, useRef, useState } from "react";
import { LogTerminal } from "@/components/LogTerminal";
import type { ExecutionLog } from "@/lib/executions";
import { fmtClock, fmtDuration, type JobTask } from "@/lib/jobs";
import { openExecutionSocket } from "@/lib/ws";
import { StatusIcon } from "@/ui";
import { NotebookIcon, RetryIcon } from "@/ui/icons";

interface Props {
  tasks: JobTask[]; // já na ordem de execução
  selectedId: string | null;
  onSelect: (task: JobTask) => void;
  runningStepByTask?: Record<string, string>; // job_task_id -> "Executando célula 12"
}

// log de execução do notebook (papermill/kernel) da tarefa, ao vivo via /ws/executions/{id}
function TaskExecutionLog({ executionId }: { executionId: string }) {
  const [logs, setLogs] = useState<ExecutionLog[]>([]);
  const seen = useRef<Set<number>>(new Set());

  useEffect(() => {
    seen.current = new Set();
    setLogs([]);
    const close = openExecutionSocket(executionId, {
      onSnapshot: (e) => {
        for (const l of e.logs) seen.current.add(l.seq);
        setLogs(e.logs);
      },
      onLog: (l) => {
        if (seen.current.has(l.seq)) return;
        seen.current.add(l.seq);
        setLogs((prev) => [...prev, l]);
      },
    });
    return close;
  }, [executionId]);

  if (logs.length === 0) {
    return <p className="py-2 text-xs text-fg-faint">Sem log do notebook ainda.</p>;
  }
  return (
    <LogTerminal
      title="Log do notebook"
      lines={logs.map((l) => ({ seq: l.seq, level: l.level, message: l.message, ts: l.ts }))}
      filename={`execution-${executionId.slice(0, 8)}.txt`}
    />
  );
}

export function TaskTimeline({ tasks, selectedId, onSelect, runningStepByTask }: Props) {
  if (tasks.length === 0) {
    return <p className="px-4 py-6 text-sm text-fg-faint">Sem tarefas.</p>;
  }
  return (
    <ol className="divide-y divide-surface-border">
      {tasks.map((t) => {
        const on = t.id === selectedId;
        const running = t.status === "RUNNING";
        const failed = t.status === "FAILED";
        const step = runningStepByTask?.[t.id];
        return (
          <li key={t.id}>
            <button
              type="button"
              onClick={() => onSelect(t)}
              className={`flex w-full items-start gap-3 px-3 py-2.5 text-left transition ${
                on ? "bg-primary/10" : "hover:bg-surface-variant"
              }`}
            >
              <StatusIcon status={t.status} className="mt-0.5 h-4 w-4 shrink-0" />
              <span className="min-w-0 flex-1">
                <span className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
                  <span className={`truncate text-sm ${failed ? "text-danger" : "text-fg"}`}>
                    {t.name}
                  </span>
                  {t.attempt > 1 && (
                    <span className="inline-flex items-center gap-0.5 rounded bg-warn/15 px-1 text-[11px] text-warn">
                      <RetryIcon className="h-3 w-3" />
                      {t.attempt}
                    </span>
                  )}
                  {t.notebook_name && (
                    <span className="inline-flex items-center gap-1 text-xs text-fg-faint">
                      <NotebookIcon className="h-3 w-3" />
                      {t.notebook_name}
                    </span>
                  )}
                </span>
                {running && (
                  <span className="mt-1 block">
                    <span className="block h-1 overflow-hidden rounded bg-info/20">
                      <span className="block h-full w-full origin-left animate-indeterminate rounded bg-info" />
                    </span>
                    {step && <span className="mt-0.5 block text-[11px] text-danger">{step}</span>}
                  </span>
                )}
                {failed && t.error_message && (
                  <span className="mt-0.5 block truncate text-xs text-danger">{t.error_message}</span>
                )}
              </span>
              <span className="flex shrink-0 flex-col items-end gap-0.5 text-xs text-fg-faint">
                <span className="tabular-nums">{fmtDuration(t.duration_ms)}</span>
                {t.started_at && <span>{fmtClock(t.started_at)}</span>}
              </span>
            </button>
            {on && (
              <div className="border-t border-surface-border bg-surface-variant/30 px-3 py-2">
                {t.execution_id ? (
                  <TaskExecutionLog executionId={t.execution_id} />
                ) : (
                  <p className="py-2 text-xs text-fg-faint">
                    Notebook ainda não começou a executar.
                  </p>
                )}
              </div>
            )}
          </li>
        );
      })}
    </ol>
  );
}
