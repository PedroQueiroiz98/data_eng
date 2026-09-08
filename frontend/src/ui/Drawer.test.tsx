import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Drawer } from "@/ui/Drawer";

describe("Drawer", () => {
  it("renderiza quando open e chama onClose no Esc / overlay / botão", () => {
    const onClose = vi.fn();
    const { rerender } = render(
      <Drawer open title="Título" onClose={onClose}>
        <p>conteúdo</p>
      </Drawer>,
    );
    expect(screen.getByText("conteúdo")).toBeInTheDocument();
    expect(screen.getByRole("dialog")).toBeInTheDocument();

    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole("button", { name: "Fechar" }));
    expect(onClose).toHaveBeenCalledTimes(2);

    rerender(
      <Drawer open={false} title="Título" onClose={onClose}>
        <p>conteúdo</p>
      </Drawer>,
    );
    expect(screen.queryByText("conteúdo")).not.toBeInTheDocument();
  });

  it("mostra o footer quando fornecido", () => {
    render(
      <Drawer open title="X" onClose={() => {}} footer={<button>Salvar</button>}>
        body
      </Drawer>,
    );
    expect(screen.getByRole("button", { name: "Salvar" })).toBeInTheDocument();
  });
});
