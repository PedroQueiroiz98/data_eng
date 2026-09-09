import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { __registered } from "@/test/monacoMock";

const h = vi.hoisted(() => ({ lspComplete: vi.fn(), lspResolve: vi.fn() }));
const lspComplete = h.lspComplete;
const lspResolve = h.lspResolve;

vi.mock("@/lib/lsp", () => ({
  lspComplete: (...a: unknown[]) => h.lspComplete(...a),
  lspResolve: (...a: unknown[]) => h.lspResolve(...a),
  lspHover: vi.fn(),
  lspSignature: vi.fn(),
  lspDefinition: vi.fn(),
  lspAutoImport: vi.fn(),
}));

vi.mock("@/lib/editorConfig", () => ({
  getEditorConfig: () => ({
    editor: { autocomplete: true, hover: true, signatureHelp: true },
  }),
}));

const SNIPPET_RULE = 4; // monacoMock: CompletionItemInsertTextRule.InsertAsSnippet
const URI = "file:///wsnb/root/nb/c1.py";

function makeToken() {
  const cbs: Array<() => void> = [];
  return {
    token: {
      isCancellationRequested: false,
      onCancellationRequested: (cb: () => void) => {
        cbs.push(cb);
        return { dispose() {} };
      },
    },
    cancel() {
      this.token.isCancellationRequested = true;
      cbs.forEach((cb) => cb());
    },
  };
}

const model = {
  uri: { toString: () => URI },
  getWordUntilPosition: () => ({ startColumn: 4, endColumn: 4 }),
  getLineContent: () => "df.",
};
const position = { lineNumber: 1, column: 4 };

let completionProvider: any;
let provide: (m: any, p: any, c: any, t: any) => Promise<any>;

beforeAll(async () => {
  const mod = await import("@/lib/monacoProviders");
  mod.registerPythonIntelligence();
  mod.setLspDoc({
    cellUris: [URI],
    getCells: () => ["df."],
    navigate: () => {},
    workspaceId: "root",
    notebookPath: "nb",
  });
  completionProvider = __registered.completion[0];
  provide = completionProvider.provideCompletionItems;
});

beforeEach(() => {
  vi.useFakeTimers();
  lspComplete.mockReset();
  lspResolve.mockReset();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("monacoProviders — completion", () => {
  it("transforma um item chamável num snippet name($0) e liga parameter hints", async () => {
    lspComplete.mockResolvedValue({
      ok: true,
      items: [
        { label: "merge", insert_text: "merge", kind: "method", detail: "", documentation: "", call: true },
        { label: "columns", insert_text: "columns", kind: "instance", detail: "", documentation: "", call: false },
      ],
    });
    const { token } = makeToken();
    const p = provide(model, position, {}, token);
    await vi.advanceTimersByTimeAsync(200);
    const res = await p;

    const merge = res.suggestions.find((s: any) => s.label === "merge");
    expect(merge.insertText).toBe("merge($0)");
    expect(merge.insertTextRules).toBe(SNIPPET_RULE);
    expect(merge.command.id).toBe("editor.action.triggerParameterHints");

    const columns = res.suggestions.find((s: any) => s.label === "columns");
    expect(columns.insertText).toBe("columns");
    expect(columns.insertTextRules).toBeUndefined();
  });

  it("cancelar o token durante o debounce evita a chamada ao backend", async () => {
    lspComplete.mockResolvedValue({ ok: true, items: [] });
    const t1 = makeToken();
    const p1 = provide(model, position, {}, t1.token);
    t1.cancel();
    const r1 = await p1;
    expect(r1.suggestions).toEqual([]);

    const t2 = makeToken();
    const p2 = provide(model, position, {}, t2.token);
    await vi.advanceTimersByTimeAsync(200);
    await p2;
    expect(lspComplete).toHaveBeenCalledTimes(1);
  });

  it("inline completions não dispara quando desabilitado", async () => {
    const inline = __registered.inlineCompletions[0];
    expect(inline).toBeTruthy();
    const { token } = makeToken();
    const res = await inline.provideInlineCompletions(model, position, {}, token);
    expect(res.items).toEqual([]);
  });

  it("resolveCompletionItem preenche detail/documentation sob demanda", async () => {
    lspResolve.mockResolvedValue({
      ok: true,
      detail: "merge(right, how='inner')",
      documentation: "Merge DataFrame.",
      kind: "method",
    });
    const item: any = {
      label: "merge",
      __lsp: { label: "merge", cellIndex: 0, line: 0, column: 3 },
    };
    const { token } = makeToken();
    const out = await completionProvider.resolveCompletionItem(item, token);
    expect(out.detail).toBe("merge(right, how='inner')");
    expect(out.documentation).toBe("Merge DataFrame.");
  });
});
