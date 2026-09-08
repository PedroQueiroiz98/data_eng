/**
 * Providers de inteligência do Monaco para Python, ligados ao backend LSP.
 *
 * O editor de notebook usa uma instância do Monaco por célula. Um "documento
 * lógico" (LspDoc) mantém a lista ordenada de URIs das células + um snapshot do
 * texto de todas elas, para o backend analisar o notebook inteiro.
 */
import * as monaco from "monaco-editor";
import { getEditorConfig } from "@/lib/editorConfig";
import { lspAutoImport, lspComplete, lspDefinition, lspHover, lspSignature } from "@/lib/lsp";

// ── Completion de caminhos de arquivo do Workspace dentro de strings ──────────
interface WorkspaceFsCtx {
  /** todos os caminhos relativos ao notebook aberto (ex.: "../data/x.csv") */
  listRelPaths: () => string[];
}
let wsFsCtx: WorkspaceFsCtx | null = null;
export function setWorkspaceFsContext(ctx: WorkspaceFsCtx | null): void {
  wsFsCtx = ctx;
}

const READ_CALL_RE =
  /(?:read_csv|read_parquet|read_json|read_excel|read_table|open|Path)\s*\(\s*(['"])([^'"]*)$/;

export interface LspDoc {
  /** URIs (model.uri.toString()) das células, na ordem do notebook. */
  cellUris: string[];
  /** Snapshot atual do texto de cada célula. */
  getCells: () => string[];
  /** Navega o editor para (célula, linha 0-based, coluna 0-based). */
  navigate: (cellIndex: number, line: number, column: number) => void;
  /** contexto do Workspace (Jedi enxerga scripts/*.py) */
  workspaceId?: string;
  notebookPath?: string;
}

let activeDoc: LspDoc | null = null;
export function setLspDoc(doc: LspDoc | null): void {
  activeDoc = doc;
}

const wsCtx = () => ({
  workspaceId: activeDoc?.workspaceId,
  notebookPath: activeDoc?.notebookPath,
});

function cellIndexOf(model: monaco.editor.ITextModel): number {
  if (!activeDoc) return -1;
  return activeDoc.cellUris.indexOf(model.uri.toString());
}

const KIND = monaco.languages.CompletionItemKind;
const KIND_MAP: Record<string, monaco.languages.CompletionItemKind> = {
  module: KIND.Module,
  class: KIND.Class,
  function: KIND.Function,
  method: KIND.Method,
  instance: KIND.Variable,
  statement: KIND.Variable,
  param: KIND.Variable,
  property: KIND.Property,
  keyword: KIND.Keyword,
  path: KIND.File,
};

let registered = false;

export function registerPythonIntelligence(): void {
  if (registered) return;
  registered = true;

  monaco.languages.registerCompletionItemProvider("python", {
    triggerCharacters: ["."],
    async provideCompletionItems(model, position, _ctx, token) {
      if (!getEditorConfig().editor.autocomplete) return { suggestions: [] };
      const idx = cellIndexOf(model);
      if (idx < 0 || !activeDoc) return { suggestions: [] };

      const res = await lspComplete({
        cells: activeDoc.getCells(),
        cellIndex: idx,
        line: position.lineNumber - 1,
        column: position.column - 1,
        ...wsCtx(),
      });
      if (token.isCancellationRequested || !res.ok) return { suggestions: [] };

      const word = model.getWordUntilPosition(position);
      const range: monaco.IRange = {
        startLineNumber: position.lineNumber,
        endLineNumber: position.lineNumber,
        startColumn: word.startColumn,
        endColumn: word.endColumn,
      };
      return {
        suggestions: res.items.map((it, i) => ({
          label: it.label,
          kind: KIND_MAP[it.kind] ?? KIND.Text,
          insertText: it.insert_text,
          detail: it.detail || undefined,
          documentation: it.documentation || undefined,
          range,
          sortText: String(i).padStart(4, "0"),
        })),
      };
    },
  });

  monaco.languages.registerHoverProvider("python", {
    async provideHover(model, position, token) {
      if (!getEditorConfig().editor.hover) return null;
      const idx = cellIndexOf(model);
      if (idx < 0 || !activeDoc) return null;
      const res = await lspHover({
        cells: activeDoc.getCells(),
        cellIndex: idx,
        line: position.lineNumber - 1,
        column: position.column - 1,
        ...wsCtx(),
      });
      if (token.isCancellationRequested || !res.ok || !res.name) return null;
      const header = res.signature
        ? `\`\`\`python\n${res.signature}\n\`\`\``
        : `**${res.kind || "symbol"}** \`${res.name}\``;
      const body = res.documentation ? `\n\n${res.documentation}` : "";
      const src = res.full_name ? `\n\n_${res.full_name}_` : "";
      return { contents: [{ value: header + body + src }] };
    },
  });

  monaco.languages.registerSignatureHelpProvider("python", {
    signatureHelpTriggerCharacters: ["(", ","],
    signatureHelpRetriggerCharacters: [","],
    async provideSignatureHelp(model, position, token) {
      if (!getEditorConfig().editor.signatureHelp) return null;
      const idx = cellIndexOf(model);
      if (idx < 0 || !activeDoc) return null;
      const res = await lspSignature({
        cells: activeDoc.getCells(),
        cellIndex: idx,
        line: position.lineNumber - 1,
        column: position.column - 1,
        ...wsCtx(),
      });
      if (token.isCancellationRequested || !res.ok || !res.label) return null;
      return {
        value: {
          signatures: [
            {
              label: res.label,
              documentation: res.documentation || undefined,
              parameters: res.parameters.map((p) => ({ label: p })),
            },
          ],
          activeSignature: 0,
          activeParameter: res.active_parameter,
        },
        dispose() {},
      };
    },
  });

  monaco.languages.registerDefinitionProvider("python", {
    async provideDefinition(model, position, token) {
      const idx = cellIndexOf(model);
      if (idx < 0 || !activeDoc) return null;
      const res = await lspDefinition({
        cells: activeDoc.getCells(),
        cellIndex: idx,
        line: position.lineNumber - 1,
        column: position.column - 1,
        ...wsCtx(),
      });
      if (token.isCancellationRequested || !res.ok) return null;
      const out: monaco.languages.Location[] = [];
      for (const loc of res.locations) {
        if (loc.external || loc.cell_index < 0) continue;
        const uri = activeDoc.cellUris[loc.cell_index];
        if (!uri) continue;
        out.push({
          uri: monaco.Uri.parse(uri),
          range: {
            startLineNumber: loc.line + 1,
            endLineNumber: loc.line + 1,
            startColumn: loc.column + 1,
            endColumn: loc.column + 1 + (loc.name.length || 1),
          },
        });
      }
      return out;
    },
  });

  // Completion de caminhos do Workspace: `pd.read_csv("../data/<aqui>`
  monaco.languages.registerCompletionItemProvider("python", {
    triggerCharacters: ['"', "'", "/"],
    provideCompletionItems(model, position) {
      if (!wsFsCtx || !getEditorConfig().editor.autocomplete) {
        return { suggestions: [] };
      }
      const line = model.getValueInRange({
        startLineNumber: position.lineNumber,
        startColumn: 1,
        endLineNumber: position.lineNumber,
        endColumn: position.column,
      });
      const m = READ_CALL_RE.exec(line);
      if (!m) return { suggestions: [] };
      const typed = m[2] ?? "";
      const slash = typed.lastIndexOf("/");
      const wordStart = position.column - (typed.length - slash - 1);
      const range: monaco.IRange = {
        startLineNumber: position.lineNumber,
        endLineNumber: position.lineNumber,
        startColumn: wordStart,
        endColumn: position.column,
      };
      const seen = new Set<string>();
      const suggestions: monaco.languages.CompletionItem[] = [];
      for (const rel of wsFsCtx.listRelPaths()) {
        if (typed && !rel.startsWith(typed)) continue;
        const rest = rel.slice(slash + 1);
        const label = rest.includes("/") ? `${rest.split("/")[0]}/` : rest;
        if (seen.has(label)) continue;
        seen.add(label);
        suggestions.push({
          label,
          kind: monaco.languages.CompletionItemKind.File,
          insertText: label,
          range,
        });
      }
      return { suggestions };
    },
  });

  // Auto-import: quick-fix para "undefined name 'X'" (nunca aplica sozinho).
  monaco.languages.registerCodeActionProvider("python", {
    async provideCodeActions(model, _range, context) {
      const idx = cellIndexOf(model);
      if (idx < 0 || !activeDoc) return { actions: [], dispose() {} };
      const firstUri = activeDoc.cellUris[0];
      if (!firstUri) return { actions: [], dispose() {} };
      const firstModel = monaco.editor.getModel(monaco.Uri.parse(firstUri));
      if (!firstModel) return { actions: [], dispose() {} };

      const names = new Set<string>();
      for (const m of context.markers) {
        const match = /undefined name '(\w+)'/.exec(m.message);
        if (match?.[1]) names.add(match[1]);
      }
      if (names.size === 0) return { actions: [], dispose() {} };

      const actions: monaco.languages.CodeAction[] = [];
      for (const name of names) {
        const res = await lspAutoImport(name);
        if (!res.ok) continue;
        for (const s of res.suggestions) {
          actions.push({
            title: s.label,
            kind: "quickfix",
            diagnostics: context.markers,
            edit: {
              edits: [
                {
                  resource: firstModel.uri,
                  versionId: firstModel.getVersionId(),
                  textEdit: {
                    range: { startLineNumber: 1, startColumn: 1, endLineNumber: 1, endColumn: 1 },
                    text: `${s.statement}\n`,
                  },
                },
              ],
            },
          });
        }
      }
      return { actions, dispose() {} };
    },
  });
}
