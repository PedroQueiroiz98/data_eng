import { apiDelete, apiGet, apiPost, apiPut, getAuthToken } from "@/lib/api";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api";

// ─── Tipos ──────────────────────────────────────────────────────────────────
export interface Workspace {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  owner_id: string | null;
  root_path: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface WorkspaceGitSummary {
  provider: string;
  repo_url: string;
  repo_owner: string | null;
  repo_name: string | null;
  default_branch: string | null;
  current_branch: string | null;
  last_sync_at: string | null;
}

export interface WorkspaceDetail extends Workspace {
  git_repository: WorkspaceGitSummary | null;
}

export interface FileNode {
  name: string;
  path: string;
  type: "file" | "dir";
  size?: number | null;
  modified_at?: number | null;
  children?: FileNode[] | null;
}

export type FileKind = "notebook" | "text" | "binary";

export interface FileContent {
  path: string;
  kind: FileKind;
  content: Record<string, unknown> | string | null;
  etag?: string | null;
}

// ─── Workspace CRUD ─────────────────────────────────────────────────────────
export const listWorkspaces = (includeInactive = false): Promise<Workspace[]> =>
  apiGet(`/workspaces?include_inactive=${includeInactive}`);

export const getWorkspace = (id: string): Promise<WorkspaceDetail> =>
  apiGet(`/workspaces/${id}`);

export const createWorkspace = (body: {
  name: string;
  description?: string;
}): Promise<WorkspaceDetail> => apiPost("/workspaces", body);

// PATCH não tem helper dedicado no api.ts → fetch direto (mesma semântica de erro).
export async function updateWorkspace(
  id: string,
  body: { name?: string; description?: string; is_active?: boolean },
): Promise<WorkspaceDetail> {
  const res = await fetch(`${API_BASE}/workspaces/${id}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      ...(getAuthToken() ? { Authorization: `Bearer ${getAuthToken()}` } : {}),
    },
    body: JSON.stringify(body),
  });
  const text = await res.text();
  const parsed = text ? JSON.parse(text) : null;
  if (!res.ok) {
    throw new Error(parsed?.error?.message ?? `PATCH /workspaces/${id} → ${res.status}`);
  }
  return parsed as WorkspaceDetail;
}

export const deleteWorkspace = (id: string, purge = false): Promise<void> =>
  apiDelete(`/workspaces/${id}?purge=${purge}`);

// ─── File Explorer ─────────────────────────────────────────────────────────
export const getTree = (id: string, path = "", depth?: number): Promise<FileNode> => {
  const qs = new URLSearchParams({ path });
  if (depth != null) qs.set("depth", String(depth));
  return apiGet(`/workspaces/${id}/tree?${qs.toString()}`);
};

export const readFile = (id: string, path: string): Promise<FileContent> =>
  apiGet(`/workspaces/${id}/file?path=${encodeURIComponent(path)}`);

export interface FilePaths {
  path: string;
  name: string;
  parent_path: string;
  workspace_path: string;
  repository_path: string;
  read_example: string | null;
}

export const getFilePaths = (
  id: string,
  path: string,
  fromPath?: string,
): Promise<FilePaths> => {
  const qs = new URLSearchParams({ path });
  if (fromPath) qs.set("from_path", fromPath);
  return apiGet(`/workspaces/${id}/file/paths?${qs.toString()}`);
};

export const writeFile = (
  id: string,
  path: string,
  body: { text?: string; notebook?: Record<string, unknown>; ifMatch?: string | null },
): Promise<FileContent> =>
  apiPut(
    `/workspaces/${id}/file?path=${encodeURIComponent(path)}`,
    { text: body.text, notebook: body.notebook },
    body.ifMatch ? { "If-Match": body.ifMatch } : undefined,
  );

export const makeDir = (id: string, path: string): Promise<FileNode> =>
  apiPost(`/workspaces/${id}/dir?path=${encodeURIComponent(path)}`);

export const deleteEntry = (id: string, path: string, recursive = false): Promise<void> =>
  apiDelete(
    `/workspaces/${id}/file?path=${encodeURIComponent(path)}&recursive=${recursive}`,
  );

export const renameEntry = (id: string, from: string, to: string): Promise<FileNode> =>
  apiPost(`/workspaces/${id}/rename`, { from, to });

export const copyEntry = (id: string, from: string, to: string): Promise<FileNode> =>
  apiPost(`/workspaces/${id}/copy`, { from, to });

export const downloadUrl = (id: string, path: string): string =>
  `${API_BASE}/workspaces/${id}/download?path=${encodeURIComponent(path)}`;

/**
 * Download autenticado (Bearer) via fetch + blob. `window.open(downloadUrl)` não
 * envia o header Authorization e retorna 401 no modo bearer-only.
 */
export async function downloadFile(id: string, path: string): Promise<void> {
  const token = getAuthToken();
  const res = await fetch(downloadUrl(id, path), {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    let msg = `download → ${res.status}`;
    try {
      msg = (JSON.parse(text) as { error?: { message?: string } })?.error?.message ?? msg;
    } catch {
      /* corpo não-JSON */
    }
    throw new Error(msg);
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  const cd = res.headers.get("Content-Disposition") ?? "";
  const m = /filename="?([^"]+)"?/.exec(cd);
  a.download = m?.[1] ?? path.split("/").pop() ?? "download";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export interface GenerateFileBody {
  path: string;
  rows: number;
  seed?: number | null;
  kind?: "csv";
}

/** Gera um arquivo sintético grande no backend (streaming em disco). */
export const generateFile = (id: string, body: GenerateFileBody): Promise<FileNode> =>
  apiPost(`/workspaces/${id}/generate`, {
    path: body.path,
    rows: body.rows,
    seed: body.seed ?? null,
    kind: body.kind ?? "csv",
  });

export interface WorkspaceExecution {
  id: string;
  status: string;
}

/** Dispara execução de produção (Papermill) de um `.ipynb` do workspace. */
export const executeWorkspaceNotebook = (
  id: string,
  notebookPath: string,
  parameters: Record<string, unknown> = {},
): Promise<WorkspaceExecution> =>
  apiPost(`/workspaces/${id}/execute`, {
    notebook_path: notebookPath,
    parameters,
  });

export async function uploadFile(
  id: string,
  dir: string,
  file: File,
): Promise<FileNode> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(
    `${API_BASE}/workspaces/${id}/upload?path=${encodeURIComponent(dir)}`,
    {
      method: "POST",
      headers: getAuthToken() ? { Authorization: `Bearer ${getAuthToken()}` } : {},
      body: form,
    },
  );
  const text = await res.text();
  const parsed = text ? JSON.parse(text) : null;
  if (!res.ok) {
    throw new Error(parsed?.error?.message ?? `upload → ${res.status}`);
  }
  return parsed as FileNode;
}
