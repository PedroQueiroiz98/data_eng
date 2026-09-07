import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Workflows } from "@/pages/Workflows";

const navigate = vi.fn();
vi.mock("react-router-dom", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-router-dom")>();
  return { ...actual, useNavigate: () => navigate };
});

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <Workflows />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

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
  it("lista workflows", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify([wf]), { status: 200 }),
    );
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("ETL Diário")).toBeInTheDocument();
      expect(screen.getByText("ACTIVE")).toBeInTheDocument();
    });
  });

  it("cria workflow e navega para o editor", async () => {
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 }))
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ ...wf, id: "w2", tasks: [], dependencies: [] }), {
          status: 201,
        }),
      )
      .mockResolvedValue(new Response(JSON.stringify([]), { status: 200 }));

    renderPage();
    await waitFor(() => expect(screen.getByText(/Nenhum workflow/)).toBeInTheDocument());
    await userEvent.type(screen.getByPlaceholderText(/Nome do novo/), "Novo WF");
    await userEvent.click(screen.getByRole("button", { name: /Novo workflow/ }));
    await waitFor(() => expect(navigate).toHaveBeenCalledWith("/workflows/w2"));
  });
});
