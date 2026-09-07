import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createNotebook,
  deleteNotebook,
  getNotebook,
  listNotebooks,
  saveNotebookVersion,
  updateNotebook,
  type NotebookContent,
} from "@/lib/notebooks";

const keys = {
  all: ["notebooks"] as const,
  detail: (id: string) => ["notebooks", id] as const,
};

export function useNotebooks() {
  return useQuery({ queryKey: keys.all, queryFn: listNotebooks });
}

export function useNotebook(id: string) {
  return useQuery({ queryKey: keys.detail(id), queryFn: () => getNotebook(id) });
}

export function useCreateNotebook() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createNotebook,
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.all }),
  });
}

export function useUpdateNotebook(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { name?: string; description?: string }) => updateNotebook(id, body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: keys.all });
      void qc.invalidateQueries({ queryKey: keys.detail(id) });
    },
  });
}

export function useDeleteNotebook() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deleteNotebook,
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.all }),
  });
}

export function useSaveVersion(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (content: NotebookContent) => saveNotebookVersion(id, content),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: keys.all });
      void qc.invalidateQueries({ queryKey: keys.detail(id) });
    },
  });
}
