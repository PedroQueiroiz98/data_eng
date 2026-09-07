import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders } from "@/test/utils";
import { Workflows } from "@/pages/Workflows";

const navigate = vi.fn();
vi.mock("react-router-dom", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-router-dom")>();
  return { ...actual, useNavigate: () => navigate };
});

afterEach(() => {
  vi.restoreAllMocks();
  navigate.mockReset();
});

const wf = {
  id: "w1",
  name: "ETL Diário",
  description: null,
  status: "ACTIVE",
  created_at: "2026-09-07T00:00:00Z",
  updated_at: "2026-09-07T00:00:00Z",
};

describe("Workflows page", () => {
  it("lista workflows com chip de status", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify([wf]), { status: 200 }),
    );
    renderWithProviders(<Workflows />);
    await waitFor(() => {
      expect(screen.getByText("ETL Diário")).toBeInTheDocument();
      expect(screen.getByText("Active")).toBeInTheDocument();
    });
  });

  it("cria workflow via dialog e navega", async () => {
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 }))
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ ...wf, id: "w2", tasks: [], dependencies: [] }), {
          status: 201,
        }),
      )
      .mockResolvedValue(new Response(JSON.stringify([]), { status: 200 }));

    renderWithProviders(<Workflows />);
    await waitFor(() => expect(screen.getByText(/Nenhum workflow/)).toBeInTheDocument());
    await userEvent.click(screen.getAllByRole("button", { name: /Novo Workflow/i })[0]!);
    await userEvent.type(screen.getByLabelText("Nome"), "Novo WF");
    await userEvent.click(screen.getByRole("button", { name: /^Criar$/ }));
    await waitFor(() => expect(navigate).toHaveBeenCalledWith("/workflows/w2"));
  });
});
