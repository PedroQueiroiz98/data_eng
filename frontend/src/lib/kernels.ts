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

// Workspace único: rota fixa `/api/workspace/kernel`. O 1º parâmetro (`_ws`) é
// mantido só por compat de assinatura das telas e é ignorado.
const K = "/workspace/kernel/sessions";

export const openKernelSession = (
  _ws: string,
  notebookPath: string,
): Promise<KernelSession> =>
  apiPost(K, { notebook_path: notebookPath });

export const getKernelSession = (_ws: string, sessionId: string): Promise<KernelSession> =>
  apiGet(`${K}/${sessionId}`);

export const executeCell = (
  _ws: string,
  sessionId: string,
  cellId: string,
  code: string,
): Promise<{ request_id: string }> =>
  apiPost(`${K}/${sessionId}/execute`, { cell_id: cellId, code });

export const interruptKernel = (_ws: string, sessionId: string): Promise<unknown> =>
  apiPost(`${K}/${sessionId}/interrupt`);

export const restartKernel = (_ws: string, sessionId: string): Promise<unknown> =>
  apiPost(`${K}/${sessionId}/restart`);

export const closeKernel = (_ws: string, sessionId: string): Promise<void> =>
  apiDelete(`${K}/${sessionId}`);
