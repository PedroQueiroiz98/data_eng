import { apiGet, apiPost } from "@/lib/api";
import type { NotebookContent } from "@/lib/notebooks";

export type ExecutionStatus =
  | "QUEUED"
  | "RUNNING"
  | "SUCCESS"
  | "FAILED"
  | "CANCELLED"
  | "TIMEOUT";

export interface Execution {
  id: string;
  notebook_version_id: string;
  status: ExecutionStatus;
  attempt: number;
  parameters: Record<string, unknown>;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  duration_ms: number | null;
  error_code: string | null;
  error_message: string | null;
  worker_id: string | null;
}

export interface ExecutionDetail extends Execution {
  output_notebook_path: string | null;
  has_output: boolean;
}

export interface ExecutionLog {
  seq: number;
  ts: string;
  level: "DEBUG" | "INFO" | "WARNING" | "ERROR";
  message: string;
  attempt: number;
}

export const TERMINAL_STATUSES: ReadonlySet<ExecutionStatus> = new Set([
  "SUCCESS",
  "FAILED",
  "CANCELLED",
  "TIMEOUT",
]);

export const isTerminal = (s: ExecutionStatus): boolean => TERMINAL_STATUSES.has(s);

export const listExecutions = (params?: {
  status?: ExecutionStatus;
}): Promise<Execution[]> => {
  const qs = params?.status ? `?status=${params.status}&limit=200` : "?limit=200";
  return apiGet<Execution[]>(`/executions${qs}`);
};

export const getExecution = (id: string): Promise<ExecutionDetail> =>
  apiGet<ExecutionDetail>(`/executions/${id}`);

export const getExecutionLogs = (id: string, afterSeq = 0): Promise<ExecutionLog[]> =>
  apiGet<ExecutionLog[]>(`/executions/${id}/logs?after_seq=${afterSeq}`);

export const getExecutionOutput = (id: string): Promise<NotebookContent> =>
  apiGet<NotebookContent>(`/executions/${id}/output`);

export const executeNotebook = (
  notebookId: string,
  body: { parameters?: Record<string, unknown>; notebook_version_number?: number },
): Promise<Execution> =>
  apiPost<Execution>(`/notebooks/${notebookId}/execute`, body);
