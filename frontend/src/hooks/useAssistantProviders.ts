import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createAssistantProvider,
  deleteAssistantProvider,
  getAssistantProvider,
  listAssistantProviders,
  setAssistantProviderEnabled,
  testAssistantProvider,
  updateAssistantProvider,
  type AssistantProviderInput,
} from "@/lib/assistantProviders";

const KEY = ["assistant-providers"];

export function useAssistantProviders() {
  return useQuery({ queryKey: KEY, queryFn: listAssistantProviders });
}

export function useAssistantProvider(id: string, enabled = true) {
  return useQuery({
    queryKey: [...KEY, id],
    queryFn: () => getAssistantProvider(id),
    enabled: enabled && !!id,
  });
}

export function useCreateAssistantProvider() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: AssistantProviderInput) => createAssistantProvider(body),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
  });
}

export function useUpdateAssistantProvider(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Partial<AssistantProviderInput>) => updateAssistantProvider(id, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
  });
}

export function useDeleteAssistantProvider() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteAssistantProvider(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
  });
}

export function useToggleAssistantProvider() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) =>
      setAssistantProviderEnabled(id, enabled),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
  });
}

export function useTestAssistantProvider() {
  return useMutation({ mutationFn: (id: string) => testAssistantProvider(id) });
}
