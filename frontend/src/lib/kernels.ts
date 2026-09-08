import { apiDelete, apiGet, apiPost } from "@/lib/api";
import type { CellOutput } from "@/lib/notebooks";

export type KernelStatus =
  | "starting"
  | "idle"
  | "busy"
  | "restarting"
  | "dead";

export interface KernelSession {
  session_id: string;
  status: KernelStatus;
  execution_count: number;
  notebook_path: string;
}

export interface KernelEvent {
  type:
    | "kernel.status"
    | "cell.started"
    | "cell.output"
    | "cell.error"
    | "cell.finished"
    | "snapshot";
  seq?: number;
  /** `kernel.status` → KernelStatus; `cell.finished` → "ok" | "error" */
  status?: KernelStatus | "ok" | "error";
  reason?: string;
  restarted?: boolean;
  cell_id?: string;
  request_id?: string;
  output?: CellOutput;
  outputs?: CellOutput[];
  execution_count?: number | null;
  duration_ms?: number;
}

export const openKernelSession = (
  workspaceId: string,
  notebookPath: string,
): Promise<KernelSession> =>
  apiPost(`/workspaces/${workspaceId}/kernel/sessions`, {
    notebook_path: notebookPath,
  });

export const getKernelSession = (
  workspaceId: string,
  sessionId: string,
): Promise<KernelSession> =>
  apiGet(`/workspaces/${workspaceId}/kernel/sessions/${sessionId}`);

export const executeCell = (
  workspaceId: string,
  sessionId: string,
  cellId: string,
  code: string,
): Promise<{ request_id: string }> =>
  apiPost(
    `/workspaces/${workspaceId}/kernel/sessions/${sessionId}/execute`,
    { cell_id: cellId, code },
  );

export const interruptKernel = (workspaceId: string, sessionId: string): Promise<unknown> =>
  apiPost(`/workspaces/${workspaceId}/kernel/sessions/${sessionId}/interrupt`);

export const restartKernel = (workspaceId: string, sessionId: string): Promise<unknown> =>
  apiPost(`/workspaces/${workspaceId}/kernel/sessions/${sessionId}/restart`);

export const closeKernel = (workspaceId: string, sessionId: string): Promise<void> =>
  apiDelete(`/workspaces/${workspaceId}/kernel/sessions/${sessionId}`);
