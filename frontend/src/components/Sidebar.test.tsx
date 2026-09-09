import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { Sidebar } from "@/components/Sidebar";

describe("Sidebar", () => {
  it("renderiza os itens de navegação como lista única", () => {
    render(
      <MemoryRouter>
        <Sidebar mobileOpen={false} onClose={() => {}} />
      </MemoryRouter>,
    );
    for (const label of [
      "Dashboard",
      "Workspace",
      "Workflows",
      "Jobs",
      "Execuções",
      "Agendamentos",
      "Notificações",
      "Variáveis",
      "Secrets",
    ]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
    expect(screen.getByText("Notificações").closest("a")).toHaveAttribute(
      "href",
      "/notifications",
    );
    expect(screen.getByText("Workspace").closest("a")).toHaveAttribute(
      "href",
      "/workspace",
    );
    // sem cabeçalhos de grupo
    expect(screen.queryByText("Administração")).not.toBeInTheDocument();
  });
});
