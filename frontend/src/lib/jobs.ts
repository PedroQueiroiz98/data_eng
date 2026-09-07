import { apiDelete, apiGet, apiPost } from "@/lib/api";

export type JobStatus = "QUEUED" | "RUNNING" | "SUCCESS" | "FAILED" | "CANCELLED";
export type JobTaskStatus =
  | "PENDING"
  | "QUEUED"
  | "RUNNING"
  | "SUCCESS"
  | "FAILED"
  | "CANCELLED"
  | "SKIPPED";

export interface Job {
  id: string;
  workflow_id: string;
  status: JobStatus;
  trigger_type: "MANUAL" | "SCHEDULED" | "API";
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  duration_ms: number | null;
  task_total: number;
  task_success: number;
  task_failed: number;
  task_running: number;
}

export interface JobTask {
  id: string;
  workflow_task_id: string;
  execution_id: string | null;
  status: JobTaskStatus;
  attempt: number;
  started_at: string | null;
  finished_at: string | null;
  duration_ms: number | null;
  error_message: string | null;
  name: string;
  notebook_id: string | null;
  notebook_name: string;
}

export interface JobDetail extends Job {
  workflow_name: string;
  started_by: string | null;
  parameters: Record<string, unknown>;
  tasks: JobTask[];
  dependencies: { from: string; to: string }[];
}

// ─── helpers de apresentação ─────────────────────────────────────────────────

export interface TaskCounts {
  total: number;
  success: number;
  failed: number;
  running: number;
  pending: number;
  skipped: number;
  cancelled: number;
}

export function taskCounts(tasks: readonly JobTask[]): TaskCounts {
  const c: TaskCounts = {
    total: tasks.length,
    success: 0,
    failed: 0,
    running: 0,
    pending: 0,
    skipped: 0,
    cancelled: 0,
  };
  for (const t of tasks) {
    if (t.status === "SUCCESS") c.success++;
    else if (t.status === "FAILED") c.failed++;
    else if (t.status === "RUNNING") c.running++;
    else if (t.status === "SKIPPED") c.skipped++;
    else if (t.status === "CANCELLED") c.cancelled++;
    else c.pending++; // PENDING | QUEUED
  }
  return c;
}

export function fmtDuration(ms: number | null | undefined): string {
  if (ms == null) return "—";
  const s = Math.round(ms / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ${String(s % 60).padStart(2, "0")}s`;
  return `${Math.floor(m / 60)}h ${String(m % 60).padStart(2, "0")}m`;
}

export function fmtClock(iso: string | null | undefined): string {
  return iso ? new Date(iso).toLocaleTimeString() : "—";
}

/** Segundos decorridos desde `startedAt` até agora (para jobs RUNNING). */
export function elapsedSince(startedAt: string | null | undefined, nowMs: number): number {
  if (!startedAt) return 0;
  return Math.max(0, Math.floor((nowMs - new Date(startedAt).getTime()) / 1000));
}

export function fmtElapsed(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

/**
 * Ordena as tarefas em camadas topológicas a partir das dependências
 * (workflow_task_id). Tarefas sem dependência entram na camada 0.
 */
export function topoLayers(
  tasks: readonly JobTask[],
  deps: readonly { from: string; to: string }[],
): JobTask[][] {
  const byWtid = new Map(tasks.map((t) => [t.workflow_task_id, t]));
  const indeg = new Map<string, number>();
  const adj = new Map<string, string[]>();
  for (const t of tasks) {
    indeg.set(t.workflow_task_id, 0);
    adj.set(t.workflow_task_id, []);
  }
  for (const d of deps) {
    if (!byWtid.has(d.from) || !byWtid.has(d.to)) continue;
    adj.get(d.from)!.push(d.to);
    indeg.set(d.to, (indeg.get(d.to) ?? 0) + 1);
  }
  let frontier = [...indeg.entries()].filter(([, n]) => n === 0).map(([id]) => id);
  const seen = new Set<string>();
  const layers: JobTask[][] = [];
  while (frontier.length) {
    const layer = frontier.filter((id) => !seen.has(id));
    if (layer.length === 0) break;
    layers.push(layer.map((id) => byWtid.get(id)!).filter(Boolean));
    for (const id of layer) seen.add(id);
    const next = new Set<string>();
    for (const id of layer) {
      for (const to of adj.get(id) ?? []) {
        indeg.set(to, (indeg.get(to) ?? 1) - 1);
        if ((indeg.get(to) ?? 0) <= 0) next.add(to);
      }
    }
    frontier = [...next];
  }
  // qualquer tarefa não visitada (ciclo/dados inconsistentes) vai numa última camada
  const leftovers = tasks.filter((t) => !seen.has(t.workflow_task_id));
  if (leftovers.length) layers.push(leftovers);
  return layers;
}

export interface JobLog {
  seq: number;
  ts: string;
  level: "DEBUG" | "INFO" | "WARNING" | "ERROR";
  message: string;
  job_task_id: string | null;
}

export const JOB_TERMINAL: ReadonlySet<JobStatus> = new Set([
  "SUCCESS",
  "FAILED",
  "CANCELLED",
]);
export const isJobTerminal = (s: JobStatus): boolean => JOB_TERMINAL.has(s);

export const listJobs = (workflowId?: string): Promise<Job[]> =>
  apiGet<Job[]>(`/jobs?limit=200${workflowId ? `&workflow_id=${workflowId}` : ""}`);

export const getJob = (id: string): Promise<JobDetail> =>
  apiGet<JobDetail>(`/jobs/${id}`);

export const getJobLogs = (id: string, afterSeq = 0): Promise<JobLog[]> =>
  apiGet<JobLog[]>(`/jobs/${id}/logs?after_seq=${afterSeq}`);

export const runWorkflow = (
  workflowId: string,
  parameters: Record<string, unknown> = {},
): Promise<Job> => apiPost<Job>(`/workflows/${workflowId}/run`, { parameters });

export const cancelJob = (id: string): Promise<Job> =>
  apiPost<Job>(`/jobs/${id}/cancel`);

export const retryJob = (id: string): Promise<Job> =>
  apiPost<Job>(`/jobs/${id}/retry`);

export const deleteJob = (id: string): Promise<void> => apiDelete(`/jobs/${id}`);
