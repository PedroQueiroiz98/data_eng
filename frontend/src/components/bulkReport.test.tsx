import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { bulkFailureReport } from "@/components/bulkReport";

describe("bulkFailureReport", () => {
  it("resume falhas parciais agrupadas por motivo", () => {
    const { title, message } = bulkFailureReport(
      {
        ok: 1,
        failed: 2,
        failures: [
          { id: "a", message: "Notebook em uso por workflow" },
          { id: "b", message: "Notebook em uso por workflow" },
        ],
      },
      3,
      "notebooks",
      (id) => `NB ${id}`,
    );
    expect(title).toMatch(/2 de 3 notebooks/);
    render(<div>{message}</div>);
    expect(screen.getByText("Notebook em uso por workflow")).toBeInTheDocument();
    expect(screen.getByText("NB a")).toBeInTheDocument();
    expect(screen.getByText("NB b")).toBeInTheDocument();
    expect(screen.getByText(/1 excluído/)).toBeInTheDocument();
  });

  it("título diferente quando nada foi excluído", () => {
    const { title } = bulkFailureReport(
      { ok: 0, failed: 1, failures: [{ id: "x", message: "erro" }] },
      1,
      "jobs",
      (id) => id,
    );
    expect(title).toMatch(/Nenhum job foi excluído/);
  });
});
