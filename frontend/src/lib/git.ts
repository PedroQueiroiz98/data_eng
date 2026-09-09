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
  merging: boolean;
  remote_configured: boolean;
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

// Workspace único: rota fixa. O 1º parâmetro `_id` é mantido só por compat de
// assinatura (as telas ainda o passam) e é ignorado.
const BASE = "/workspace/git";

export const gitStatus = (_id?: string): Promise<GitStatus> => apiGet(`${BASE}/status`);

export const gitDiff = (
  _id?: string,
  path?: string,
): Promise<{ path: string | null; diff: string }> =>
  apiGet(`${BASE}/diff${path ? `?path=${encodeURIComponent(path)}` : ""}`);

export const gitLog = (_id?: string, limit = 50): Promise<GitCommitEntry[]> =>
  apiGet(`${BASE}/log?limit=${limit}`);

export const gitBranches = (_id?: string): Promise<GitBranches> => apiGet(`${BASE}/branches`);

export const gitInit = (_id?: string): Promise<GitStatus> => apiPost(`${BASE}/init`);

export const gitCreateBranch = (_id: string, name: string): Promise<{ branch: string }> =>
  apiPost(`${BASE}/branches`, { name });

export const gitCheckout = (_id: string, ref: string): Promise<{ ref: string }> =>
  apiPost(`${BASE}/checkout`, { ref });

export const gitCommit = (
  _id: string,
  message: string,
  paths: string[],
): Promise<{ sha: string }> => apiPost(`${BASE}/commit`, { message, paths });

export const gitDiscard = (_id: string, paths: string[]): Promise<{ discarded: number }> =>
  apiPost(`${BASE}/discard`, { paths });

export interface GitPullResult {
  conflicts: string[];
}

export const gitRemoteLink = (
  _id: string,
  repoFullName: string,
  branch: string,
  baseDir: string,
): Promise<GitPullResult> =>
  apiPost(`${BASE}/remote`, { repo_full_name: repoFullName, branch, base_dir: baseDir });

export const gitPush = (_id?: string): Promise<{ branch: string }> => apiPost(`${BASE}/push`);

export const gitPull = (_id?: string): Promise<GitPullResult> => apiPost(`${BASE}/pull`);

export const gitMergeAbort = (_id?: string): Promise<{ aborted: boolean }> =>
  apiPost(`${BASE}/merge/abort`);
