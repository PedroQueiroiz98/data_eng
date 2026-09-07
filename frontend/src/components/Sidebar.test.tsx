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
      "Notebooks",
      "Workflows",
      "Jobs",
      "Execuções",
      "Agendamentos",
      "Variáveis",
      "Secrets",
    ]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
    // sem cabeçalhos de grupo
    expect(screen.queryByText("Workspace")).not.toBeInTheDocument();
    expect(screen.queryByText("Administração")).not.toBeInTheDocument();
  });
});
