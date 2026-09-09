import { apiDelete, apiGet, apiPost } from "@/lib/api";

export interface GitHubAccount {
  connected: boolean;
  username: string | null;
  email: string | null;
  avatar_url: string | null;
  repo_full_name: string | null;
  repo_default_branch: string | null;
  base_dir: string | null;
  last_sync_at: string | null;
}

export interface GitHubRepo {
  full_name: string;
  private: boolean;
  default_branch: string;
  clone_url: string;
  updated_at: string;
}

export interface GitHubBranch {
  name: string;
}

export const githubStatus = (): Promise<GitHubAccount> => apiGet("/github/status");

export const githubConnect = (token: string): Promise<GitHubAccount> =>
  apiPost("/github/auth", { token });

export const githubDisconnect = (): Promise<void> => apiDelete("/github/auth");

export const githubRepos = (): Promise<GitHubRepo[]> => apiGet("/github/repos");

export const githubBranches = (repoFullName: string): Promise<GitHubBranch[]> =>
  apiGet(`/github/repos/${repoFullName}/branches`);
