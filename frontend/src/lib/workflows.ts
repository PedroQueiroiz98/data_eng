import { apiDelete, apiGet, apiPost, apiPut } from "@/lib/api";

export type WorkflowStatus = "DRAFT" | "ACTIVE" | "DISABLED" | "ARCHIVED";
export type TaskType = "NOTEBOOK" | "PYTHON";

export interface Workflow {
  id: string;
  name: string;
  description: string | null;
  status: WorkflowStatus;
  created_at: string;
  updated_at: string;
}

export interface WorkflowTask {
  id: string;
  name: string;
  type: TaskType;
  notebook_id: string | null;
  workspace_id: string | null;
  notebook_path: string | null;
  parameters: Record<string, unknown>;
  timeout_s: number | null;
  max_retries: number;
  retry_policy: Record<string, unknown>;
  ui_position: { x: number; y: number } | null;
}

export interface WorkflowDependency {
  id: string;
  from_task_id: string;
  to_task_id: string;
}

export interface WorkflowDetail extends Workflow {
  tasks: WorkflowTask[];
  dependencies: WorkflowDependency[];
}

export interface TaskInput {
  key: string;
  name: string;
  type?: TaskType;
  notebook_id?: string | null;
  workspace_id?: string | null;
  notebook_path?: string | null;
  parameters?: Record<string, unknown>;
  timeout_s?: number | null;
  max_retries?: number;
  retry_policy?: Record<string, unknown>;
  ui_position?: { x: number; y: number } | null;
}

export interface GraphSave {
  tasks: TaskInput[];
  dependencies: { from_key: string; to_key: string }[];
}

// ─── API ────────────────────────────────────────────────────────────────────

export const listWorkflows = (): Promise<Workflow[]> =>
  apiGet<Workflow[]>("/workflows?limit=200");

export const getWorkflow = (id: string): Promise<WorkflowDetail> =>
  apiGet<WorkflowDetail>(`/workflows/${id}`);

export const createWorkflow = (body: {
  name: string;
  description?: string;
}): Promise<WorkflowDetail> => apiPost<WorkflowDetail>("/workflows", body);

export const updateWorkflow = (
  id: string,
  body: { name?: string; description?: string; status?: WorkflowStatus },
): Promise<WorkflowDetail> => apiPut<WorkflowDetail>(`/workflows/${id}`, body);

export const deleteWorkflow = (id: string): Promise<void> =>
  apiDelete(`/workflows/${id}`);

export const saveWorkflowGraph = (
  id: string,
  graph: GraphSave,
): Promise<WorkflowDetail> => apiPut<WorkflowDetail>(`/workflows/${id}/graph`, graph);

// ─── Helper puro (testável sem React Flow) ──────────────────────────────────

export interface FlowNodeLike {
  id: string;
  position: { x: number; y: number };
  data: {
    name: string;
    notebookId: string | null;
    workspaceId?: string | null;
    notebookPath?: string | null;
    timeoutS: number | null;
    maxRetries: number;
  };
}

export interface FlowEdgeLike {
  source: string;
  target: string;
}

export function buildGraphPayload(
  nodes: FlowNodeLike[],
  edges: FlowEdgeLike[],
): GraphSave {
  return {
    tasks: nodes.map((n) => ({
      key: n.id,
      name: n.data.name,
      type: "NOTEBOOK",
      notebook_id: n.data.workspaceId ? null : n.data.notebookId,
      workspace_id: n.data.workspaceId ?? null,
      notebook_path: n.data.notebookPath ?? null,
      timeout_s: n.data.timeoutS,
      max_retries: n.data.maxRetries,
      ui_position: { x: Math.round(n.position.x), y: Math.round(n.position.y) },
    })),
    dependencies: edges.map((e) => ({ from_key: e.source, to_key: e.target })),
  };
}
