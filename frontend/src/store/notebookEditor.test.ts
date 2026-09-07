import { beforeEach, describe, expect, it } from "vitest";
import { useNotebookEditor } from "@/store/notebookEditor";
import type { NotebookContent } from "@/lib/notebooks";

const baseContent: NotebookContent = {
  nbformat: 4,
  nbformat_minor: 5,
  metadata: { language_info: { name: "python" } },
  cells: [
    { cell_type: "code", source: "# Parameters\n", metadata: { tags: ["parameters"] } },
    { cell_type: "code", source: "print(1)", metadata: {}, outputs: [], execution_count: null },
  ],
};

const store = () => useNotebookEditor.getState();

beforeEach(() => {
  useNotebookEditor.setState({ cells: [], selectedId: null, dirty: false });
  store().load(structuredClone(baseContent));
});

describe("notebookEditor store", () => {
  it("carrega células e não fica dirty", () => {
    expect(store().cells).toHaveLength(2);
    expect(store().dirty).toBe(false);
    expect(store().cells[0]!.metadata.tags).toContain("parameters");
  });

  it("addCell insere abaixo da referência e seleciona", () => {
    const firstId = store().cells[0]!.localId;
    store().addCell("markdown", firstId);
    expect(store().cells).toHaveLength(3);
    expect(store().cells[1]!.cell_type).toBe("markdown");
    expect(store().selectedId).toBe(store().cells[1]!.localId);
    expect(store().dirty).toBe(true);
  });

  it("removeCell remove a célula certa", () => {
    const secondId = store().cells[1]!.localId;
    store().removeCell(secondId);
    expect(store().cells).toHaveLength(1);
    expect(store().cells.find((c) => c.localId === secondId)).toBeUndefined();
  });

  it("duplicateCell copia sem outputs e insere após", () => {
    const id = store().cells[1]!.localId;
    store().setSource(id, "print('x')");
    store().duplicateCell(id);
    expect(store().cells).toHaveLength(3);
    expect(store().cells[2]!.source).toBe("print('x')");
    expect(store().cells[2]!.outputs).toEqual([]);
  });

  it("moveCell troca a ordem e respeita limites", () => {
    const [a, b] = [store().cells[0]!.localId, store().cells[1]!.localId];
    store().moveCell(b, "up");
    expect(store().cells.map((c) => c.localId)).toEqual([b, a]);
    store().moveCell(b, "up"); // já no topo: no-op
    expect(store().cells.map((c) => c.localId)).toEqual([b, a]);
  });

  it("setCellType para markdown remove campos de código", () => {
    const id = store().cells[1]!.localId;
    store().setCellType(id, "markdown");
    const cell = store().cells[1]!;
    expect(cell.cell_type).toBe("markdown");
    expect(cell.outputs).toBeUndefined();
  });

  it("toContent devolve estrutura .ipynb serializável", () => {
    store().setSource(store().cells[1]!.localId, "y = 2");
    const content = store().toContent();
    expect(content.nbformat).toBe(4);
    expect(content.cells).toHaveLength(2);
    expect(content.cells[1]!.source).toBe("y = 2");
    expect(content.cells[1]!.execution_count).toBeNull();
    // sem localId no payload
    expect("localId" in content.cells[1]!).toBe(false);
  });

  it("markSaved limpa o dirty", () => {
    store().addCell("code", null);
    expect(store().dirty).toBe(true);
    store().markSaved();
    expect(store().dirty).toBe(false);
  });

  it("carrega dependências de metadata.nbplatform e as reescreve em toContent", () => {
    store().load(
      structuredClone({
        ...baseContent,
        metadata: {
          language_info: { name: "python" },
          nbplatform: { dependencies: ["psycopg[binary]", "requests"] },
        },
      }),
    );
    expect(store().dependencies).toBe("psycopg[binary]\nrequests");

    store().setDependencies("pandas==2.2.2\n# comentário\n\nnumpy");
    expect(store().dirty).toBe(true);
    const meta = store().toContent().metadata as Record<string, unknown>;
    expect((meta.nbplatform as Record<string, unknown>).dependencies).toEqual([
      "pandas==2.2.2",
      "numpy",
    ]);
    expect((meta.language_info as Record<string, unknown>).name).toBe("python");
  });

  it("toContent remove nbplatform.dependencies quando a lista fica vazia", () => {
    store().load(
      structuredClone({
        ...baseContent,
        metadata: { nbplatform: { dependencies: ["requests"] } },
      }),
    );
    store().setDependencies("   \n# só comentário");
    const meta = store().toContent().metadata as Record<string, unknown>;
    expect(meta.nbplatform).toBeUndefined();
  });
});
