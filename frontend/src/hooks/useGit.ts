import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  gitBranches,
  gitCheckout,
  gitCommit,
  gitCreateBranch,
  gitDiff,
  gitDiscard,
  gitInit,
  gitLog,
  gitStatus,
} from "@/lib/git";

const keys = {
  status: (id: string) => ["git", id, "status"] as const,
  branches: (id: string) => ["git", id, "branches"] as const,
  log: (id: string) => ["git", id, "log"] as const,
  diff: (id: string, path?: string) => ["git", id, "diff", path ?? "*"] as const,
};

export function useGitStatus(id: string, enabled = true) {
  return useQuery({
    queryKey: keys.status(id),
    queryFn: () => gitStatus(id),
    enabled,
    refetchInterval: enabled ? 5000 : false,
  });
}

export function useGitBranches(id: string, enabled = true) {
  return useQuery({
    queryKey: keys.branches(id),
    queryFn: () => gitBranches(id),
    enabled,
  });
}

export function useGitLog(id: string, enabled = true) {
  return useQuery({ queryKey: keys.log(id), queryFn: () => gitLog(id), enabled });
}

export function useGitDiff(id: string, path: string | undefined, enabled: boolean) {
  return useQuery({
    queryKey: keys.diff(id, path),
    queryFn: () => gitDiff(id, path),
    enabled,
  });
}

function useInvalidateGit(id: string) {
  const qc = useQueryClient();
  return () => void qc.invalidateQueries({ queryKey: ["git", id] });
}

export function useGitInit(id: string) {
  const inv = useInvalidateGit(id);
  return useMutation({ mutationFn: () => gitInit(id), onSuccess: inv });
}

export function useGitCommit(id: string) {
  const inv = useInvalidateGit(id);
  return useMutation({
    mutationFn: ({ message, paths }: { message: string; paths: string[] }) =>
      gitCommit(id, message, paths),
    onSuccess: inv,
  });
}

export function useGitCreateBranch(id: string) {
  const inv = useInvalidateGit(id);
  return useMutation({
    mutationFn: (name: string) => gitCreateBranch(id, name),
    onSuccess: inv,
  });
}

export function useGitCheckout(id: string) {
  const inv = useInvalidateGit(id);
  return useMutation({ mutationFn: (ref: string) => gitCheckout(id, ref), onSuccess: inv });
}

export function useGitDiscard(id: string) {
  const inv = useInvalidateGit(id);
  return useMutation({
    mutationFn: (paths: string[]) => gitDiscard(id, paths),
    onSuccess: inv,
  });
}
