import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Executions } from "@/pages/Executions";

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <Executions />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.restoreAllMocks());

const exec = {
  id: "abcdef12-0000-0000-0000-000000000000",
  notebook_version_id: "v1",
  status: "SUCCESS",
  attempt: 1,
  parameters: {},
  created_at: "2026-09-07T00:00:00Z",
  started_at: null,
  finished_at: null,
  duration_ms: 3540,
  error_code: null,
  error_message: null,
  worker_id: "w1",
};

describe("Executions page", () => {
  it("lista execuções com status e duração", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify([exec]), { status: 200 }),
    );
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("SUCCESS")).toBeInTheDocument();
      expect(screen.getByText("abcdef12")).toBeInTheDocument();
      expect(screen.getByText("3.5s")).toBeInTheDocument();
    });
  });

  it("mostra estado vazio", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify([]), { status: 200 }),
    );
    renderPage();
    await waitFor(() =>
      expect(screen.getByText(/Nenhuma execução ainda/)).toBeInTheDocument(),
    );
  });
});
