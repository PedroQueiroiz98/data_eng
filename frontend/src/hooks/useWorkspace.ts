import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  copyEntry,
  createWorkspace,
  deleteEntry,
  deleteWorkspace,
  getTree,
  getWorkspace,
  listWorkspaces,
  makeDir,
  readFile,
  renameEntry,
  updateWorkspace,
  writeFile,
} from "@/lib/workspace";

const keys = {
  all: ["workspaces"] as const,
  detail: (id: string) => ["workspaces", id] as const,
  tree: (id: string, path: string) => ["workspaces", id, "tree", path] as const,
  file: (id: string, path: string) => ["workspaces", id, "file", path] as const,
};

export function useWorkspaces(includeInactive = false) {
  return useQuery({
    queryKey: [...keys.all, { includeInactive }],
    queryFn: () => listWorkspaces(includeInactive),
  });
}

export function useWorkspace(id: string) {
  return useQuery({ queryKey: keys.detail(id), queryFn: () => getWorkspace(id) });
}

export function useCreateWorkspace() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createWorkspace,
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.all }),
  });
}

export function useUpdateWorkspace(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { name?: string; description?: string; is_active?: boolean }) =>
      updateWorkspace(id, body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: keys.all });
      void qc.invalidateQueries({ queryKey: keys.detail(id) });
    },
  });
}

export function useDeleteWorkspace() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, purge }: { id: string; purge?: boolean }) =>
      deleteWorkspace(id, purge),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.all }),
  });
}

export function useWorkspaceTree(id: string, path = "") {
  return useQuery({
    queryKey: keys.tree(id, path),
    queryFn: () => getTree(id, path),
  });
}

export function useWorkspaceFile(id: string, path: string | null) {
  return useQuery({
    queryKey: keys.file(id, path ?? ""),
    queryFn: () => readFile(id, path as string),
    enabled: !!path,
  });
}

/** Invalida a árvore inteira do workspace (qualquer subcaminho). */
function invalidateTree(qc: ReturnType<typeof useQueryClient>, id: string) {
  void qc.invalidateQueries({ queryKey: ["workspaces", id, "tree"] });
}

export function useWriteFile(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      path,
      text,
      notebook,
      ifMatch,
    }: {
      path: string;
      text?: string;
      notebook?: Record<string, unknown>;
      ifMatch?: string | null;
    }) => writeFile(id, path, { text, notebook, ifMatch }),
    onSuccess: (_data, vars) => {
      invalidateTree(qc, id);
      void qc.invalidateQueries({ queryKey: keys.file(id, vars.path) });
    },
  });
}

export function useMakeDir(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (path: string) => makeDir(id, path),
    onSuccess: () => invalidateTree(qc, id),
  });
}

export function useDeleteEntry(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ path, recursive }: { path: string; recursive?: boolean }) =>
      deleteEntry(id, path, recursive),
    onSuccess: () => invalidateTree(qc, id),
  });
}

export function useRenameEntry(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ from, to }: { from: string; to: string }) => renameEntry(id, from, to),
    onSuccess: () => invalidateTree(qc, id),
  });
}

export function useCopyEntry(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ from, to }: { from: string; to: string }) => copyEntry(id, from, to),
    onSuccess: () => invalidateTree(qc, id),
  });
}
