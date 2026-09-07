import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Jobs } from "@/pages/Jobs";

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <Jobs />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.restoreAllMocks());

const job = {
  id: "job12345-0000-0000-0000-000000000000",
  workflow_id: "w1",
  status: "SUCCESS",
  trigger_type: "MANUAL",
  created_at: "2026-09-07T00:00:00Z",
  started_at: null,
  finished_at: null,
  duration_ms: 151000,
};

describe("Jobs page", () => {
  it("lista jobs com status e duração", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify([job]), { status: 200 }),
    );
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("SUCCESS")).toBeInTheDocument();
      expect(screen.getByText("job12345")).toBeInTheDocument();
      expect(screen.getByText(/2m 31s/)).toBeInTheDocument();
    });
  });

  it("mostra estado vazio", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify([]), { status: 200 }),
    );
    renderPage();
    await waitFor(() =>
      expect(screen.getByText(/Nenhum job ainda/)).toBeInTheDocument(),
    );
  });
});
