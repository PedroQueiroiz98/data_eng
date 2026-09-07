import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useCancelJob, useJob, useRetryJob } from "@/hooks/useJobs";
import {
  isJobTerminal,
  type JobLog,
  type JobStatus,
  type JobTask,
  type JobTaskStatus,
} from "@/lib/jobs";
import { openJobSocket } from "@/lib/ws";

const TASK_ICON: Record<JobTaskStatus, string> = {
  PENDING: "○",
  QUEUED: "◔",
  RUNNING: "◐",
  SUCCESS: "✓",
  FAILED: "✕",
  CANCELLED: "⊘",
  SKIPPED: "→",
};
const TASK_COLOR: Record<JobTaskStatus, string> = {
  PENDING: "text-slate-300",
  QUEUED: "text-slate-400",
  RUNNING: "text-blue-600",
  SUCCESS: "text-green-600",
  FAILED: "text-red-600",
  CANCELLED: "text-slate-500",
  SKIPPED: "text-amber-600",
};

export function JobDetail() {
  const { id = "" } = useParams();
  const cancel = useCancelJob(id);
  const retry = useRetryJob(id);

  const [status, setStatus] = useState<JobStatus | null>(null);
  const [workflowName, setWorkflowName] = useState("");
  const [tasks, setTasks] = useState<JobTask[]>([]);
  const [logs, setLogs] = useState<JobLog[]>([]);
  const [connected, setConnected] = useState(false);
  const [nonce, setNonce] = useState(0);

  const restEnabled = status == null || !isJobTerminal(status);
  const { data: rest } = useJob(id, restEnabled);
  const effective = status ?? rest?.status ?? null;

  useEffect(() => {
    setLogs([]);
    const seen = new Set<number>();
    const close = openJobSocket(id, {
      onOpen: () => setConnected(true),
      onDisconnect: () => setConnected(false),
      onSnapshot: (e) => {
        setStatus(e.job.status);
        setWorkflowName(e.job.workflow_name);
        setTasks(e.tasks);
        for (const l of e.logs) seen.add(l.seq);
        setLogs(e.logs);
      },
      onLog: (l) => {
        if (seen.has(l.seq)) return;
        seen.add(l.seq);
        setLogs((prev) => [
          ...prev,
          { seq: l.seq, ts: "", level: "INFO", message: l.message, job_task_id: l.job_task_id },
        ]);
      },
      onStatus: (s) => setStatus(s),
      onProgress: () => {}, // rest query + próximos logs cobrem o refresh das tasks
    });
    return close;
  }, [id, nonce]);

  // tasks vêm do snapshot + fallback REST (o WS só reenvia snapshot ao reconectar)
  const shownTasks = tasks.length ? tasks : (rest?.tasks ?? []);

  const onRetry = async () => {
    await retry.mutateAsync();
    setStatus("RUNNING");
    setNonce((n) => n + 1);
  };

  return (
    <div className="mx-auto max-w-3xl">
      <div className="mb-4 flex items-center gap-3">
        <Link to="/jobs" className="text-sm text-slate-500 hover:underline">
          ← Jobs
        </Link>
        <span className="font-mono text-sm text-slate-500">{id.slice(0, 8)}</span>
        <span className="text-sm font-medium">{workflowName || rest?.workflow_name}</span>
        {effective && <span className="text-sm text-slate-600">· {effective}</span>}
        <div className="ml-auto flex items-center gap-2">
          {effective && !isJobTerminal(effective) && (
            <button
              type="button"
              onClick={() => cancel.mutate()}
              disabled={cancel.isPending}
              className="rounded border border-slate-300 px-2 py-1 text-xs hover:bg-slate-50 disabled:opacity-40"
            >
              Cancelar
            </button>
          )}
          {effective && (effective === "FAILED" || effective === "CANCELLED") && (
            <button
              type="button"
              onClick={onRetry}
              disabled={retry.isPending}
              className="rounded bg-slate-800 px-2 py-1 text-xs text-white disabled:opacity-40"
            >
              Refazer falhas
            </button>
          )}
          <span className={`text-xs ${connected ? "text-green-600" : "text-slate-400"}`}>
            {connected ? "● ao vivo" : "○"}
          </span>
        </div>
      </div>

      <section className="mb-5">
        <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
          Tarefas
        </h2>
        <ul className="divide-y divide-slate-100 rounded border border-slate-200">
          {shownTasks.map((t) => (
            <li key={t.id} className="flex items-center gap-3 px-4 py-2 text-sm">
              <span className={`text-lg ${TASK_COLOR[t.status]}`} aria-hidden>
                {TASK_ICON[t.status]}
              </span>
              <span className="text-slate-700">{t.name}</span>
              <span className="text-xs text-slate-400">{t.status}</span>
              {t.error_message && (
                <span className="text-xs text-red-600">{t.error_message}</span>
              )}
              <span className="ml-auto flex gap-2 text-xs text-slate-400">
                {t.attempt > 1 && <span>#{t.attempt}</span>}
                {t.execution_id && (
                  <Link
                    to={`/executions/${t.execution_id}`}
                    className="text-blue-700 hover:underline"
                  >
                    logs
                  </Link>
                )}
              </span>
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
          Timeline
        </h2>
        <div className="max-h-80 overflow-auto rounded border border-slate-200 bg-slate-900 p-3 font-mono text-xs text-slate-100">
          {logs.length === 0 && <span className="text-slate-500">sem eventos ainda…</span>}
          {logs.map((l) => (
            <div key={l.seq}>
              <span className="text-slate-500">{String(l.seq).padStart(3, "0")} </span>
              {l.message}
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
