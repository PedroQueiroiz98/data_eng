import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { DataTable, type Column } from "@/ui/DataTable";

interface Row {
  id: string;
  name: string;
}
const rows: Row[] = [
  { id: "a", name: "Alpha" },
  { id: "b", name: "Bravo" },
  { id: "c", name: "Charlie" },
];
const columns: Column<Row>[] = [
  { key: "name", header: "Nome", render: (r) => r.name, sortValue: (r) => r.name },
];

describe("DataTable — seleção múltipla", () => {
  it("seleciona linhas e expõe os ids na barra de ações", () => {
    const bulk = vi.fn((ids: string[]) => <span>excluir {ids.length}</span>);
    render(
      <DataTable
        columns={columns}
        rows={rows}
        rowKey={(r) => r.id}
        selectable
        bulkActions={bulk}
      />,
    );
    // 1 checkbox de cabeçalho + 3 de linha
    const boxes = screen.getAllByRole("checkbox");
    expect(boxes).toHaveLength(4);

    fireEvent.click(boxes[1]!); // Alpha
    fireEvent.click(boxes[3]!); // Charlie
    expect(screen.getByText("2 selecionado(s)")).toBeInTheDocument();
    expect(bulk).toHaveBeenLastCalledWith(["a", "c"], expect.any(Function));
  });

  it("'selecionar todos' marca e desmarca todas as linhas", () => {
    render(
      <DataTable
        columns={columns}
        rows={rows}
        rowKey={(r) => r.id}
        selectable
        bulkActions={(ids) => <span>{ids.length}</span>}
      />,
    );
    const head = screen.getByLabelText("Selecionar todos");
    fireEvent.click(head);
    expect(screen.getByText("3 selecionado(s)")).toBeInTheDocument();
    fireEvent.click(head);
    expect(screen.queryByText(/selecionado\(s\)/)).not.toBeInTheDocument();
  });

  it("não mostra checkboxes quando selectable é falso", () => {
    render(<DataTable columns={columns} rows={rows} rowKey={(r) => r.id} />);
    expect(screen.queryAllByRole("checkbox")).toHaveLength(0);
  });
});
