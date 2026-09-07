import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  executeNotebook,
  getExecution,
  getExecutionOutput,
  listExecutions,
  type ExecutionStatus,
} from "@/lib/executions";

const keys = {
  list: (status?: ExecutionStatus) => ["executions", { status: status ?? null }] as const,
  detail: (id: string) => ["executions", id] as const,
  output: (id: string) => ["executions", id, "output"] as const,
};

export function useExecutions(status?: ExecutionStatus) {
  return useQuery({
    queryKey: keys.list(status),
    queryFn: () => listExecutions(status ? { status } : undefined),
    refetchInterval: 4000,
  });
}

export function useExecution(id: string, enablePolling: boolean) {
  return useQuery({
    queryKey: keys.detail(id),
    queryFn: () => getExecution(id),
    refetchInterval: enablePolling ? 3000 : false,
  });
}

export function useExecutionOutput(id: string, enabled: boolean) {
  return useQuery({
    queryKey: keys.output(id),
    queryFn: () => getExecutionOutput(id),
    enabled,
    retry: false,
  });
}

export function useExecuteNotebook(notebookId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { parameters?: Record<string, unknown> }) =>
      executeNotebook(notebookId, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["executions"] }),
  });
}
