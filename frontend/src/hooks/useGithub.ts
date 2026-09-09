import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  githubBranches,
  githubConnect,
  githubDisconnect,
  githubRepos,
  githubStatus,
} from "@/lib/github";

const keys = {
  status: ["github", "status"] as const,
  repos: ["github", "repos"] as const,
  branches: (repo: string) => ["github", "branches", repo] as const,
};

export function useGithubStatus() {
  return useQuery({ queryKey: keys.status, queryFn: githubStatus });
}

export function useGithubRepos(enabled: boolean) {
  return useQuery({ queryKey: keys.repos, queryFn: githubRepos, enabled });
}

export function useGithubBranches(repoFullName: string | null) {
  return useQuery({
    queryKey: keys.branches(repoFullName ?? ""),
    queryFn: () => githubBranches(repoFullName as string),
    enabled: !!repoFullName,
  });
}

export function useConnectGithub() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (token: string) => githubConnect(token),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["github"] }),
  });
}

export function useDisconnectGithub() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => githubDisconnect(),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["github"] }),
  });
}
