import { apiGet, apiPost } from "@/lib/api";

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
}

export interface JobDetail extends Job {
  workflow_name: string;
  tasks: JobTask[];
  dependencies: { from: string; to: string }[];
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
