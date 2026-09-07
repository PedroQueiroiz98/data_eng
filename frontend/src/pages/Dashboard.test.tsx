import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Dashboard } from "@/pages/Dashboard";

function renderWithQuery() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <Dashboard />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("Dashboard", () => {
  it("lista os serviços a partir de /ready", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          status: "ok",
          checks: {
            postgres: { ok: true, detail: null },
            redis: { ok: true, detail: null },
            worker: { ok: true, detail: "2s" },
            scheduler: { ok: true, detail: "1s" },
          },
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );

    renderWithQuery();

    await waitFor(() => {
      expect(screen.getByText("PostgreSQL")).toBeInTheDocument();
      expect(screen.getByText("Worker")).toBeInTheDocument();
      expect(screen.getByText(/operacional/)).toBeInTheDocument();
    });
  });

  it("mostra estado degradado quando um serviço falha", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          status: "degraded",
          checks: {
            postgres: { ok: true, detail: null },
            redis: { ok: false, detail: "ping failed" },
            worker: { ok: false, detail: "sem heartbeat" },
            scheduler: { ok: true, detail: "1s" },
          },
        }),
        { status: 503, headers: { "Content-Type": "application/json" } },
      ),
    );

    renderWithQuery();

    await waitFor(() => {
      expect(screen.getByText(/degradado/)).toBeInTheDocument();
      expect(screen.getByText("ping failed")).toBeInTheDocument();
    });
  });
});
