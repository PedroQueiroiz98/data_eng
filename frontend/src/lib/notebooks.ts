import { apiDelete, apiGet, apiPost, apiPut } from "@/lib/api";

// ─── Tipos .ipynb (subconjunto usado no editor) ───────────────────────────────

export type CellType = "code" | "markdown" | "raw";

export interface CellOutput {
  output_type: "stream" | "execute_result" | "display_data" | "error";
  name?: string;
  text?: string | string[];
  data?: Record<string, unknown>;
  ename?: string;
  evalue?: string;
  traceback?: string[];
}

export interface NotebookCell {
  id?: string;
  cell_type: CellType;
  source: string | string[];
  metadata: { tags?: string[] } & Record<string, unknown>;
  outputs?: CellOutput[];
  execution_count?: number | null;
}

export interface NotebookContent {
  nbformat: number;
  nbformat_minor: number;
  metadata: Record<string, unknown>;
  cells: NotebookCell[];
}

// ─── Tipos da API ────────────────────────────────────────────────────────────

export interface Notebook {
  id: string;
  name: string;
  description: string | null;
  current_version: number;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface NotebookDetail extends Notebook {
  content: NotebookContent | null;
  version_count: number;
}

export interface NotebookVersionMeta {
  id: string;
  notebook_id: string;
  version_number: number;
  created_by: string | null;
  created_at: string;
}

export interface NotebookVersionDetail extends NotebookVersionMeta {
  content: NotebookContent;
}

// ─── Chamadas ────────────────────────────────────────────────────────────────

export const listNotebooks = (): Promise<Notebook[]> =>
  apiGet<Notebook[]>("/notebooks?limit=200");

export const getNotebook = (id: string): Promise<NotebookDetail> =>
  apiGet<NotebookDetail>(`/notebooks/${id}`);

export const createNotebook = (body: {
  name: string;
  description?: string;
}): Promise<NotebookDetail> => apiPost<NotebookDetail>("/notebooks", body);

export const updateNotebook = (
  id: string,
  body: { name?: string; description?: string },
): Promise<NotebookDetail> => apiPut<NotebookDetail>(`/notebooks/${id}`, body);

export const deleteNotebook = (id: string): Promise<void> =>
  apiDelete(`/notebooks/${id}`);

export const saveNotebookVersion = (
  id: string,
  content: NotebookContent,
): Promise<NotebookVersionDetail> =>
  apiPost<NotebookVersionDetail>(`/notebooks/${id}/versions`, { content });

export const listNotebookVersions = (id: string): Promise<NotebookVersionMeta[]> =>
  apiGet<NotebookVersionMeta[]>(`/notebooks/${id}/versions`);

// ─── Helpers de célula ───────────────────────────────────────────────────────

export const cellText = (cell: NotebookCell): string =>
  Array.isArray(cell.source) ? cell.source.join("") : cell.source;

export const outputText = (output: CellOutput): string => {
  if (output.text) {
    return Array.isArray(output.text) ? output.text.join("") : output.text;
  }
  if (output.output_type === "error") {
    return [output.ename, output.evalue].filter(Boolean).join(": ");
  }
  const plain = output.data?.["text/plain"];
  if (typeof plain === "string") return plain;
  if (Array.isArray(plain)) return plain.join("");
  return "";
};
