import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders } from "@/test/utils";
import { Notebooks } from "@/pages/Notebooks";

const navigate = vi.fn();
vi.mock("react-router-dom", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-router-dom")>();
  return { ...actual, useNavigate: () => navigate };
});

afterEach(() => {
  vi.restoreAllMocks();
  navigate.mockReset();
});

const nb = {
  id: "n1",
  name: "ETL Clientes",
  description: null,
  current_version: 3,
  created_by: null,
  created_at: "2026-09-07T00:00:00Z",
  updated_at: "2026-09-07T00:00:00Z",
};

describe("Notebooks page", () => {
  it("lista notebooks da API", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify([nb]), { status: 200 }),
    );
    renderWithProviders(<Notebooks />);
    await waitFor(() => expect(screen.getByText("ETL Clientes")).toBeInTheDocument());
    expect(screen.getByText("v3")).toBeInTheDocument();
  });

  it("cria notebook via dialog e navega para o editor", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 }))
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ ...nb, id: "new1", name: "Novo" }), { status: 201 }),
      )
      .mockResolvedValue(new Response(JSON.stringify([]), { status: 200 }));

    renderWithProviders(<Notebooks />);
    await waitFor(() => expect(screen.getByText(/Nenhum notebook/)).toBeInTheDocument());

    await userEvent.click(screen.getAllByRole("button", { name: /Novo Notebook/i })[0]!);
    await userEvent.type(screen.getByLabelText("Nome"), "Novo");
    await userEvent.click(screen.getByRole("button", { name: /^Criar$/ }));

    await waitFor(() => expect(navigate).toHaveBeenCalledWith("/notebooks/new1"));
    const createCall = fetchMock.mock.calls.find(([u]) => String(u).endsWith("/notebooks"));
    expect((createCall?.[1] as RequestInit)?.method).toBe("POST");
  });
});
