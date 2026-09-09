import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  copyEntry,
  deleteEntry,
  generateFile,
  type GenerateFileBody,
  getTree,
  getWorkspace,
  makeDir,
  readFile,
  renameEntry,
  writeFile,
} from "@/lib/workspace";

/** Workspace único: chaves sem id. */
const keys = {
  detail: ["workspace"] as const,
  tree: (path: string) => ["workspace", "tree", path] as const,
  file: (path: string) => ["workspace", "file", path] as const,
};

export function useWorkspace() {
  return useQuery({ queryKey: keys.detail, queryFn: getWorkspace });
}

export function useWorkspaceTree(path = "") {
  return useQuery({ queryKey: keys.tree(path), queryFn: () => getTree(path) });
}

export function useWorkspaceFile(path: string | null) {
  return useQuery({
    queryKey: keys.file(path ?? ""),
    queryFn: () => readFile(path as string),
    enabled: !!path,
  });
}

/** Invalida a árvore inteira (qualquer subcaminho). */
function invalidateTree(qc: ReturnType<typeof useQueryClient>) {
  void qc.invalidateQueries({ queryKey: ["workspace", "tree"] });
}

/** Invalida árvore + todos os conteúdos de arquivo em cache (rename/delete/move). */
function invalidateWorkspace(qc: ReturnType<typeof useQueryClient>) {
  void qc.invalidateQueries({ queryKey: ["workspace", "tree"] });
  void qc.invalidateQueries({ queryKey: ["workspace", "file"] });
}

export function useWriteFile() {
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
    }) => writeFile(path, { text, notebook, ifMatch }),
    onSuccess: (_data, vars) => {
      invalidateTree(qc);
      void qc.invalidateQueries({ queryKey: keys.file(vars.path) });
    },
  });
}

export function useMakeDir() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (path: string) => makeDir(path),
    onSuccess: () => invalidateTree(qc),
  });
}

export function useDeleteEntry() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ path, recursive }: { path: string; recursive?: boolean }) =>
      deleteEntry(path, recursive),
    onSuccess: () => invalidateWorkspace(qc),
  });
}

export function useRenameEntry() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ from, to }: { from: string; to: string }) => renameEntry(from, to),
    onSuccess: () => invalidateWorkspace(qc),
  });
}

export function useCopyEntry() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ from, to }: { from: string; to: string }) => copyEntry(from, to),
    onSuccess: () => invalidateTree(qc),
  });
}

export function useGenerateFile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: GenerateFileBody) => generateFile(body),
    onSuccess: (_data, vars) => {
      invalidateTree(qc);
      void qc.invalidateQueries({ queryKey: keys.file(vars.path) });
    },
  });
}
