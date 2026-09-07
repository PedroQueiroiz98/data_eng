import { beforeEach, describe, expect, it } from "vitest";
import { DEFAULT_CONFIG, useEditorConfig } from "@/lib/editorConfig";

const KEY = "nbp.editor.config";

beforeEach(() => {
  localStorage.clear();
  useEditorConfig.setState({ config: structuredClone(DEFAULT_CONFIG) });
});

describe("editorConfig", () => {
  it("tem autocomplete/diagnostics/hover ligados por padrão e IA desligada", () => {
    const { config } = useEditorConfig.getState();
    expect(config.editor.autocomplete).toBe(true);
    expect(config.editor.diagnostics).toBe(true);
    expect(config.ai.enabled).toBe(false);
    expect(config.python.languageServer).toBe("jedi");
  });

  it("setSection faz merge e persiste no localStorage", () => {
    useEditorConfig.getState().setSection("editor", { diagnostics: false });
    expect(useEditorConfig.getState().config.editor.diagnostics).toBe(false);
    expect(useEditorConfig.getState().config.editor.autocomplete).toBe(true);
    const raw = JSON.parse(localStorage.getItem(KEY)!);
    expect(raw.editor.diagnostics).toBe(false);
  });

  it("setSection para IA não afeta as opções do editor", () => {
    useEditorConfig.getState().setSection("ai", { enabled: true });
    const { config } = useEditorConfig.getState();
    expect(config.ai.enabled).toBe(true);
    expect(config.editor.hover).toBe(true);
  });

  it("reset volta aos padrões", () => {
    useEditorConfig.getState().setSection("editor", { autocomplete: false });
    useEditorConfig.getState().reset();
    expect(useEditorConfig.getState().config).toEqual(DEFAULT_CONFIG);
  });
});
