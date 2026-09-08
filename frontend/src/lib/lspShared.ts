/** Helpers do editor inteligente sem dependência do monaco-editor (testáveis). */
import { type LspLocation } from "@/lib/lsp";

/** Caminho (URI) estável do model Monaco de uma célula (editor legado). */
export function cellModelPath(notebookId: string, localId: string): string {
  return `file:///nb/${notebookId || "draft"}/${localId}.py`;
}

/** Idem para uma célula de notebook do Workspace. Precisa bater exatamente com
 *  `model.uri.toString()` (usado como `<Editor path>` e em `LspDoc.cellUris`). */
export function wsCellModelPath(
  workspaceId: string,
  notebookPath: string,
  cellId: string,
): string {
  const safe = notebookPath.replace(/[^A-Za-z0-9._-]+/g, "_");
  return `file:///wsnb/${workspaceId}/${safe}/${cellId}.py`;
}

/** Rótulo legível de uma Location para os painéis. */
export function locationLabel(loc: LspLocation): string {
  if (loc.external) {
    const file = loc.external_path?.split(/[\\/]/).pop() ?? loc.module_name;
    return `${file}:${loc.line + 1}`;
  }
  return `Célula ${loc.cell_index + 1}, linha ${loc.line + 1}`;
}
