import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { cancelJob, deleteJob, getJob, listJobs, retryJob, runWorkflow } from "@/lib/jobs";

const keys = {
  list: (workflowId?: string) => ["jobs", { workflowId: workflowId ?? null }] as const,
  detail: (id: string) => ["jobs", id] as const,
};

export function useJobs(workflowId?: string) {
  return useQuery({
    queryKey: keys.list(workflowId),
    queryFn: () => listJobs(workflowId),
    refetchInterval: 4000,
  });
}

export function useJob(id: string, polling: boolean) {
  return useQuery({
    queryKey: keys.detail(id),
    queryFn: () => getJob(id),
    refetchInterval: polling ? 3000 : false,
  });
}

export function useRunWorkflow(workflowId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (parameters: Record<string, unknown>) =>
      runWorkflow(workflowId, parameters),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["jobs"] }),
  });
}

export function useCancelJob(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => cancelJob(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["jobs"] }),
  });
}

export function useRetryJob(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => retryJob(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["jobs"] }),
  });
}

export function useDeleteJob() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteJob(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["jobs"] }),
  });
}
