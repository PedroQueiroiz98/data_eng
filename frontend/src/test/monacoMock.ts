/**
 * Stub leve do `monaco-editor` para os testes (o pacote real é ESM pesado e não
 * resolve no ambiente de teste). Cobre só a superfície que o código toca.
 * Ligado via `test.alias` no `vite.config.ts`.
 */

/* eslint-disable @typescript-eslint/no-explicit-any */

export interface RegisteredProviders {
  completion: any[];
  hover: any[];
  signature: any[];
  definition: any[];
  codeAction: any[];
  inlineCompletions: any[];
}

export const __registered: RegisteredProviders = {
  completion: [],
  hover: [],
  signature: [],
  definition: [],
  codeAction: [],
  inlineCompletions: [],
};

export function __resetRegistered(): void {
  __registered.completion = [];
  __registered.hover = [];
  __registered.signature = [];
  __registered.definition = [];
  __registered.codeAction = [];
  __registered.inlineCompletions = [];
}

const disposable = { dispose() {} };

export const languages = {
  CompletionItemKind: {
    Method: 0,
    Function: 1,
    Constructor: 2,
    Field: 3,
    Variable: 4,
    Class: 5,
    Struct: 6,
    Interface: 7,
    Module: 8,
    Property: 9,
    Event: 10,
    Operator: 11,
    Unit: 12,
    Value: 13,
    Constant: 14,
    Enum: 15,
    EnumMember: 16,
    Keyword: 17,
    Text: 18,
    Color: 19,
    File: 20,
    Reference: 21,
    Customcolor: 22,
    Folder: 23,
    TypeParameter: 24,
    User: 25,
    Issue: 26,
    Snippet: 27,
  },
  CompletionItemInsertTextRule: { KeepWhitespace: 1, InsertAsSnippet: 4 },
  registerCompletionItemProvider: (_lang: string, p: any) => {
    __registered.completion.push(p);
    return disposable;
  },
  registerHoverProvider: (_lang: string, p: any) => {
    __registered.hover.push(p);
    return disposable;
  },
  registerSignatureHelpProvider: (_lang: string, p: any) => {
    __registered.signature.push(p);
    return disposable;
  },
  registerDefinitionProvider: (_lang: string, p: any) => {
    __registered.definition.push(p);
    return disposable;
  },
  registerCodeActionProvider: (_lang: string, p: any) => {
    __registered.codeAction.push(p);
    return disposable;
  },
  registerInlineCompletionsProvider: (_lang: string, p: any) => {
    __registered.inlineCompletions.push(p);
    return disposable;
  },
};

export const editor = {
  getModel: () => null,
  getModels: () => [],
  setModelMarkers: () => {},
  createDiffEditor: () => ({ setModel() {}, dispose() {} }),
};

export const Uri = {
  parse: (s: string) => ({ toString: () => s, path: s }),
};

export const MarkerSeverity = { Hint: 1, Info: 2, Warning: 4, Error: 8 };

export const KeyMod = { CtrlCmd: 2048, Shift: 1024, Alt: 512, WinCtrl: 256 };
export const KeyCode = { KeyK: 41, F12: 70, Enter: 3 };

export default { languages, editor, Uri, MarkerSeverity, KeyMod, KeyCode };
