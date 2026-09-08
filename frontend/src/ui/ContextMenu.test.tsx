import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { useContextMenu, type ContextMenuEntry } from "@/ui/ContextMenu";

function Harness({ entries }: { entries: ContextMenuEntry[] }) {
  const { open, menu } = useContextMenu();
  return (
    <div>
      <button
        type="button"
        data-testid="target"
        onContextMenu={(e) => open(e, entries)}
      >
        alvo
      </button>
      <button type="button" data-testid="outside">
        fora
      </button>
      {menu}
    </div>
  );
}

describe("useContextMenu", () => {
  it("dispara a ação do item ao clicar (não fecha no mousedown do próprio item)", async () => {
    const onClick = vi.fn();
    render(<Harness entries={[{ label: "Renomear", onClick }]} />);

    fireEvent.contextMenu(screen.getByTestId("target"));
    const item = await screen.findByRole("menuitem", { name: "Renomear" });

    // mousedown no item NÃO pode desmontar o menu antes do click
    fireEvent.mouseDown(item);
    expect(screen.queryByRole("menuitem", { name: "Renomear" })).not.toBeNull();

    fireEvent.click(item);
    expect(onClick).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("menu")).toBeNull();
  });

  it("fecha ao interagir fora do menu, sem disparar ação", async () => {
    const onClick = vi.fn();
    render(<Harness entries={[{ label: "Excluir", onClick }]} />);

    fireEvent.contextMenu(screen.getByTestId("target"));
    await screen.findByRole("menuitem", { name: "Excluir" });

    // espera o listener "armar" (attach adiado 1 tick)
    await new Promise((r) => setTimeout(r, 5));
    fireEvent.mouseDown(screen.getByTestId("outside"));

    expect(screen.queryByRole("menu")).toBeNull();
    expect(onClick).not.toHaveBeenCalled();
  });

  it("fecha com Escape", async () => {
    render(<Harness entries={[{ label: "Abrir", onClick: vi.fn() }]} />);
    fireEvent.contextMenu(screen.getByTestId("target"));
    await screen.findByRole("menu");

    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.queryByRole("menu")).toBeNull();
  });
});
