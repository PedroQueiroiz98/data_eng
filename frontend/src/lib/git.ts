import { apiGet, apiPost } from "@/lib/api";

export interface GitChange {
  path: string;
  index: string;
  worktree: string;
}

export interface GitStatus {
  initialized: boolean;
  branch: string | null;
  detached: boolean;
  ahead: number;
  behind: number;
  changes: GitChange[];
}

export interface GitCommitEntry {
  sha: string;
  author: string;
  date: string;
  subject: string;
}

export interface GitBranches {
  current: string | null;
  branches: string[];
}

const base = (id: string) => `/workspaces/${id}/git`;

export const gitStatus = (id: string): Promise<GitStatus> => apiGet(`${base(id)}/status`);

export const gitDiff = (id: string, path?: string): Promise<{ path: string | null; diff: string }> =>
  apiGet(`${base(id)}/diff${path ? `?path=${encodeURIComponent(path)}` : ""}`);

export const gitLog = (id: string, limit = 50): Promise<GitCommitEntry[]> =>
  apiGet(`${base(id)}/log?limit=${limit}`);

export const gitBranches = (id: string): Promise<GitBranches> => apiGet(`${base(id)}/branches`);

export const gitInit = (id: string): Promise<GitStatus> => apiPost(`${base(id)}/init`);

export const gitCreateBranch = (id: string, name: string): Promise<{ branch: string }> =>
  apiPost(`${base(id)}/branches`, { name });

export const gitCheckout = (id: string, ref: string): Promise<{ ref: string }> =>
  apiPost(`${base(id)}/checkout`, { ref });

export const gitCommit = (
  id: string,
  message: string,
  paths: string[],
): Promise<{ sha: string }> => apiPost(`${base(id)}/commit`, { message, paths });

export const gitDiscard = (id: string, paths: string[]): Promise<{ discarded: number }> =>
  apiPost(`${base(id)}/discard`, { paths });
