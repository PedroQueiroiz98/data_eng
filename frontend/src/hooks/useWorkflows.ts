import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createWorkflow,
  deleteWorkflow,
  getWorkflow,
  listWorkflows,
  saveWorkflowGraph,
  updateWorkflow,
  type GraphSave,
  type WorkflowStatus,
} from "@/lib/workflows";

const keys = {
  all: ["workflows"] as const,
  detail: (id: string) => ["workflows", id] as const,
};

export function useWorkflows() {
  return useQuery({ queryKey: keys.all, queryFn: listWorkflows });
}

export function useWorkflow(id: string) {
  return useQuery({ queryKey: keys.detail(id), queryFn: () => getWorkflow(id) });
}

export function useCreateWorkflow() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createWorkflow,
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.all }),
  });
}

export function useDeleteWorkflow() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deleteWorkflow,
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.all }),
  });
}

export function useUpdateWorkflow(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { name?: string; description?: string; status?: WorkflowStatus }) =>
      updateWorkflow(id, body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: keys.all });
      void qc.invalidateQueries({ queryKey: keys.detail(id) });
    },
  });
}

export function useSaveGraph(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (graph: GraphSave) => saveWorkflowGraph(id, graph),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.detail(id) }),
  });
}
