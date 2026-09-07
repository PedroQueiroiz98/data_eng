import { describe, expect, it } from "vitest";
import { cellModelPath, locationLabel } from "@/lib/lspShared";
import type { LspLocation } from "@/lib/lsp";

const base: LspLocation = {
  cell_index: 0,
  line: 0,
  column: 0,
  name: "foo",
  external: false,
  external_path: null,
  module_name: "",
  preview: "",
};

describe("lspShared", () => {
  it("cellModelPath é estável e único por (notebook, célula)", () => {
    expect(cellModelPath("nb1", "c1")).toBe("file:///nb/nb1/c1.py");
    expect(cellModelPath("nb1", "c1")).toBe(cellModelPath("nb1", "c1"));
    expect(cellModelPath("nb1", "c1")).not.toBe(cellModelPath("nb1", "c2"));
  });

  it("cellModelPath usa 'draft' quando não há id de notebook", () => {
    expect(cellModelPath("", "c1")).toBe("file:///nb/draft/c1.py");
  });

  it("locationLabel formata célula interna 1-based", () => {
    expect(locationLabel({ ...base, cell_index: 2, line: 4 })).toBe("Célula 3, linha 5");
  });

  it("locationLabel formata definição externa com nome do arquivo", () => {
    expect(
      locationLabel({
        ...base,
        external: true,
        external_path: "/usr/lib/python3.12/site-packages/pandas/core/frame.py",
        line: 41,
      }),
    ).toBe("frame.py:42");
  });
});
