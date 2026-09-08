/**
 * Tipos e helpers do formato `.ipynb`. O módulo global de notebooks (tabela
 * `notebooks`, `/api/notebooks`, página `/notebooks`) foi removido — notebooks
 * agora são arquivos dentro do Workspace. Estes tipos continuam sendo usados por
 * execuções, kernel e pelos renderers de output.
 */

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
