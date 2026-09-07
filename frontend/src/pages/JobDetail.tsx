import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { LogTerminal } from "@/components/LogTerminal";
import { useCancelJob, useJob, useRetryJob } from "@/hooks/useJobs";
import { isJobTerminal, type JobLog, type JobStatus, type JobTask } from "@/lib/jobs";
import { openJobSocket } from "@/lib/ws";
import { Button, Card, PageHeader, StatusChip, useConfirm, useToast } from "@/ui";
import { RetryIcon, StopIcon, ViewIcon } from "@/ui/icons";

function fmt(ms: number | null): string {
  if (ms == null) return "";
  const s = Math.round(ms / 1000);
  return s < 60 ? `${s}s` : `${Math.floor(s / 60)}m ${s % 60}s`;
}

export function JobDetail() {
  const { id = "" } = useParams();
  const toast = useToast();
  const confirm = useConfirm();
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
      onProgress: () => {},
    });
    return close;
  }, [id, nonce]);

  const shownTasks = tasks.length ? tasks : (rest?.tasks ?? []);

  const onRetry = async () => {
    await retry.mutateAsync();
    toast.success("Reexecutando tarefas com falha");
    setStatus("RUNNING");
    setNonce((n) => n + 1);
  };

  const onCancel = async () => {
    if (
      await confirm({
        title: "Cancelar job",
        message: "Cancelar este job e suas tarefas pendentes?",
        confirmLabel: "Cancelar job",
        cancelLabel: "Voltar",
        danger: true,
      })
    ) {
      cancel.mutate(undefined, {
        onSuccess: () => toast.success("Cancelamento solicitado"),
        onError: (e) => toast.error((e as Error).message),
      });
    }
  };

  return (
    <div>
      <PageHeader
        back={{ to: "/jobs", label: "Jobs" }}
        title={
          <span className="flex items-center gap-3">
            <span>{workflowName || rest?.workflow_name || id.slice(0, 8)}</span>
            {effective && <StatusChip status={effective} />}
          </span>
        }
        subtitle={
          <span className="flex items-center gap-3 text-xs">
            <span className="font-mono">{id.slice(0, 8)}</span>
            <span className={connected ? "text-green-600" : "text-slate-400"}>
              {connected ? "● ao vivo" : "○"}
            </span>
          </span>
        }
        actions={
          <>
            {effective && !isJobTerminal(effective) && (
              <Button
                variant="outlined"
                size="sm"
                icon={<StopIcon className="h-4 w-4" />}
                loading={cancel.isPending}
                onClick={onCancel}
              >
                Cancelar
              </Button>
            )}
            {effective && (effective === "FAILED" || effective === "CANCELLED") && (
              <Button
                size="sm"
                icon={<RetryIcon className="h-4 w-4" />}
                loading={retry.isPending}
                onClick={onRetry}
              >
                Refazer falhas
              </Button>
            )}
          </>
        }
      />

      <section className="mb-6">
        <h2 className="mb-2 text-sm font-semibold text-slate-700">Tarefas</h2>
        <Card padded={false}>
          <ul className="divide-y divide-surface-border">
            {shownTasks.map((t) => (
              <li key={t.id} className="flex items-center gap-3 px-4 py-2.5 text-sm">
                <StatusChip status={t.status} size="sm" />
                <span className="font-medium text-slate-700">{t.name}</span>
                {t.error_message && (
                  <span className="truncate text-xs text-red-600">{t.error_message}</span>
                )}
                <span className="ml-auto flex items-center gap-2 text-xs text-slate-400">
                  {t.attempt > 1 && <span>#{t.attempt}</span>}
                  {t.duration_ms != null && <span className="tabular-nums">{fmt(t.duration_ms)}</span>}
                  {t.execution_id && (
                    <Link
                      to={`/executions/${t.execution_id}`}
                      className="inline-flex items-center gap-1 text-primary hover:underline"
                    >
                      <ViewIcon className="h-3.5 w-3.5" /> logs
                    </Link>
                  )}
                </span>
              </li>
            ))}
            {shownTasks.length === 0 && (
              <li className="px-4 py-6 text-sm text-slate-400">Sem tarefas.</li>
            )}
          </ul>
        </Card>
      </section>

      <LogTerminal
        title="Timeline"
        lines={logs.map((l) => ({ seq: l.seq, level: l.level, message: l.message }))}
        filename={`job-${id.slice(0, 8)}.txt`}
      />
    </div>
  );
}
