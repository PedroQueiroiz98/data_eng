import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { LogTerminal } from "@/components/LogTerminal";
import { JobSummary } from "@/components/jobs/JobSummary";
import { PipelineGraph } from "@/components/jobs/PipelineGraph";
import { RunHistory } from "@/components/jobs/RunHistory";
import { TaskDetailPanel } from "@/components/jobs/TaskDetailPanel";
import { TaskTimeline } from "@/components/jobs/TaskTimeline";
import { useCancelJob, useJob, useJobs, useRetryJob } from "@/hooks/useJobs";
import {
  elapsedSince,
  fmtElapsed,
  isJobTerminal,
  topoLayers,
  type JobLog,
  type JobStatus,
  type JobTask,
} from "@/lib/jobs";
import { openJobSocket } from "@/lib/ws";
import { Button, Card, PageHeader, StatusChip, Tabs, useConfirm, useToast } from "@/ui";
import { RetryIcon, StopIcon } from "@/ui/icons";

const RETRYABLE_TASK = new Set(["FAILED", "CANCELLED", "SKIPPED"]);

export function JobDetail() {
  const { id = "" } = useParams();
  const toast = useToast();
  const confirm = useConfirm();
  const cancel = useCancelJob(id);
  const retry = useRetryJob(id);

  const [status, setStatus] = useState<JobStatus | null>(null);
  const [wsJob, setWsJob] = useState<Record<string, unknown> | null>(null);
  const [tasks, setTasks] = useState<JobTask[]>([]);
  const [logs, setLogs] = useState<JobLog[]>([]);
  const [connected, setConnected] = useState(false);
  const [nonce, setNonce] = useState(0);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [view, setView] = useState<"list" | "graph">("list");
  const [tab, setTab] = useState("logs");
  const [nowMs, setNowMs] = useState(() => Date.now());

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
        setWsJob(e.job as unknown as Record<string, unknown>);
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

  // relógio para o tempo decorrido de jobs em execução
  useEffect(() => {
    if (effective !== "RUNNING") return;
    const t = setInterval(() => setNowMs(Date.now()), 1000);
    return () => clearInterval(t);
  }, [effective]);

  const shownTasks = tasks.length ? tasks : (rest?.tasks ?? []);
  const dependencies = useMemo(
    () =>
      (wsJob?.dependencies as { from: string; to: string }[] | undefined) ??
      rest?.dependencies ??
      [],
    [wsJob, rest],
  );
  const orderedTasks = useMemo(
    () => topoLayers(shownTasks, dependencies).flat(),
    [shownTasks, dependencies],
  );

  const pipelineName =
    (wsJob?.workflow_name as string) || rest?.workflow_name || id.slice(0, 8);
  const startedBy = (wsJob?.started_by as string) ?? rest?.started_by ?? null;
  const parameters = useMemo(
    () =>
      (wsJob?.parameters as Record<string, unknown> | undefined) ?? rest?.parameters ?? {},
    [wsJob, rest],
  );
  const startedAt = (wsJob?.started_at as string) ?? rest?.started_at ?? null;
  const finishedAt = (wsJob?.finished_at as string) ?? rest?.finished_at ?? null;
  const durationMs = (wsJob?.duration_ms as number) ?? rest?.duration_ms ?? null;
  const trigger = (wsJob?.trigger_type as string) ?? rest?.trigger_type ?? "MANUAL";
  const workflowId = (wsJob?.workflow_id as string) ?? rest?.workflow_id ?? "";

  // seleção default: 1ª running, senão 1ª failed
  useEffect(() => {
    if (selectedTaskId && orderedTasks.some((t) => t.id === selectedTaskId)) return;
    const pick =
      orderedTasks.find((t) => t.status === "RUNNING") ??
      orderedTasks.find((t) => t.status === "FAILED") ??
      orderedTasks[0];
    setSelectedTaskId(pick?.id ?? null);
  }, [orderedTasks, selectedTaskId]);

  const selectedTask = orderedTasks.find((t) => t.id === selectedTaskId) ?? null;

  // "etapa atual" da tarefa em execução = última linha de log associada a ela (ou geral)
  const runningStepByTask = useMemo(() => {
    const out: Record<string, string> = {};
    for (const t of orderedTasks) {
      if (t.status !== "RUNNING") continue;
      const line = [...logs].reverse().find((l) => l.job_task_id === t.id);
      if (line) out[t.id] = line.message.slice(0, 80);
    }
    return out;
  }, [orderedTasks, logs]);

  const elapsedLabel =
    effective === "RUNNING" ? fmtElapsed(elapsedSince(startedAt, nowMs)) : undefined;

  // histórico do mesmo pipeline
  const { data: history } = useJobs(workflowId || undefined);
  const runNumberById = useMemo(() => {
    const m = new Map<string, number>();
    (history ?? [])
      .slice()
      .sort((a, b) => a.created_at.localeCompare(b.created_at))
      .forEach((j, i) => m.set(j.id, i + 1));
    return m;
  }, [history]);
  const runNumber = runNumberById.get(id);

  const canRetryJob = effective === "FAILED" || effective === "CANCELLED";

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

  const tabs = [
    { id: "logs", label: "Logs" },
    { id: "params", label: "Parâmetros", badge: Object.keys(parameters).length || undefined },
    { id: "history", label: "Histórico" },
  ];

  return (
    <div>
      <PageHeader
        back={{ to: "/jobs", label: "Execuções" }}
        title={
          <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <span>{pipelineName}</span>
            {runNumber != null && (
              <span className="text-sm font-normal text-fg-faint">Run #{runNumber}</span>
            )}
            {effective && <StatusChip status={effective} />}
          </span>
        }
        subtitle={
          <span className="flex items-center gap-3 text-xs">
            <span className="font-mono">{id.slice(0, 8)}</span>
            <span className={connected ? "text-ok" : "text-fg-faint"}>
              {connected ? "● ao vivo" : "○ reconectando"}
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
            {canRetryJob && (
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

      {effective && (
        <JobSummary
          status={effective}
          durationMs={durationMs}
          startedAt={startedAt}
          finishedAt={finishedAt}
          trigger={trigger}
          startedBy={startedBy}
          tasks={shownTasks}
          elapsedLabel={elapsedLabel}
        />
      )}

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <section className="lg:col-span-2">
          <div className="mb-2 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-fg">Jobs</h2>
            <div className="flex items-center gap-0.5 rounded-md border border-surface-border p-0.5">
              {(["list", "graph"] as const).map((v) => (
                <button
                  key={v}
                  type="button"
                  onClick={() => setView(v)}
                  className={`rounded px-2.5 py-1 text-xs transition ${
                    view === v
                      ? "bg-primary text-primary-fg"
                      : "text-fg-muted hover:bg-surface-variant"
                  }`}
                >
                  {v === "list" ? "Lista" : "Gráfico"}
                </button>
              ))}
            </div>
          </div>
          <Card padded={false}>
            {view === "list" ? (
              <TaskTimeline
                tasks={orderedTasks}
                selectedId={selectedTaskId}
                onSelect={(t) => setSelectedTaskId(t.id)}
                runningStepByTask={runningStepByTask}
              />
            ) : orderedTasks.length ? (
              <PipelineGraph
                tasks={shownTasks}
                dependencies={dependencies}
                selectedId={selectedTaskId}
                onSelect={(t) => setSelectedTaskId(t.id)}
              />
            ) : (
              <p className="px-4 py-6 text-sm text-fg-faint">Sem tarefas.</p>
            )}
          </Card>
        </section>

        <aside>
          <h2 className="mb-2 text-sm font-semibold text-fg">Detalhe</h2>
          {selectedTask ? (
            <TaskDetailPanel
              task={selectedTask}
              parameters={parameters}
              canRetry={canRetryJob && RETRYABLE_TASK.has(selectedTask.status)}
              retrying={retry.isPending}
              onRetry={onRetry}
              runningStep={runningStepByTask[selectedTask.id]}
              elapsedLabel={elapsedLabel}
            />
          ) : (
            <Card>
              <p className="text-sm text-fg-faint">Selecione uma tarefa para ver os detalhes.</p>
            </Card>
          )}
        </aside>
      </div>

      <div className="mt-6">
        <Tabs tabs={tabs} active={tab} onChange={setTab} />
        <div className="mt-3">
          {tab === "logs" && (
            <LogTerminal
              title="Console"
              lines={logs.map((l) => ({
                seq: l.seq,
                level: l.level,
                message: l.message,
                ts: l.ts || undefined,
              }))}
              filename={`job-${id.slice(0, 8)}.txt`}
            />
          )}
          {tab === "params" && (
            <Card>
              {Object.keys(parameters).length === 0 ? (
                <p className="text-sm text-fg-faint">Sem parâmetros.</p>
              ) : (
                <dl className="grid gap-1 font-mono text-sm sm:grid-cols-2">
                  {Object.entries(parameters).map(([k, v]) => (
                    <div key={k} className="flex gap-2">
                      <dt className="text-fg-muted">{k}</dt>
                      <dd className="min-w-0 truncate text-fg">= {String(v)}</dd>
                    </div>
                  ))}
                </dl>
              )}
              <p className="mt-3 text-xs text-fg-faint">
                Valores de chaves sensíveis (senha, token, secret…) são mascarados.
              </p>
            </Card>
          )}
          {tab === "history" && (
            <Card padded={false}>
              <RunHistory
                jobs={history ?? []}
                currentId={id}
                runNumberById={runNumberById}
              />
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
