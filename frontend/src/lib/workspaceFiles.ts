/**
 * Helpers de caminho e classificação de arquivos do Workspace.
 * `kind` dirige qual editor/visualizador a aba abre (ver `EditorSurface`).
 */

export type TabKind =
  | "notebook"
  | "code"
  | "json"
  | "csv"
  | "parquet"
  | "markdown"
  | "text";

const EXT_KIND: Record<string, TabKind> = {
  ipynb: "notebook",
  py: "code",
  sql: "code",
  js: "code",
  ts: "code",
  tsx: "code",
  jsx: "code",
  sh: "code",
  rb: "code",
  go: "code",
  r: "code",
  yaml: "code",
  yml: "code",
  toml: "code",
  ini: "code",
  cfg: "code",
  json: "json",
  csv: "csv",
  tsv: "csv",
  parquet: "parquet",
  md: "markdown",
  markdown: "markdown",
};

export function extOf(path: string): string {
  const base = path.split("/").pop() ?? "";
  const i = base.lastIndexOf(".");
  return i > 0 ? base.slice(i + 1).toLowerCase() : "";
}

export function kindFromPath(path: string): TabKind {
  return EXT_KIND[extOf(path)] ?? "text";
}

export function baseName(path: string): string {
  return path.split("/").pop() ?? path;
}

export function dirName(path: string): string {
  const i = path.lastIndexOf("/");
  return i >= 0 ? path.slice(0, i) : "";
}

export function joinPath(dir: string, name: string): string {
  return dir ? `${dir}/${name}` : name;
}

/** Caminho lógico "absoluto" exibido ao usuário (não expõe o `/data/...` real). */
export function logicalAbsPath(workspaceId: string, rel: string): string {
  return `/workspaces/${workspaceId}/${rel}`;
}

/** `"relatorio.ipynb"` → `"relatorio copy.ipynb"` (para Duplicate). */
export function duplicateName(name: string): string {
  const i = name.lastIndexOf(".");
  if (i <= 0) return `${name} copy`;
  return `${name.slice(0, i)} copy${name.slice(i)}`;
}
