import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Schedules } from "@/pages/Schedules";

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <Schedules />
    </QueryClientProvider>,
  );
}

afterEach(() => vi.restoreAllMocks());

const schedule = {
  id: "s1",
  workflow_id: "w1",
  cron: "*/10 * * * *",
  timezone: "UTC",
  enabled: true,
  parameters: {},
  last_run_at: null,
  next_run_at: "2026-09-07T12:00:00Z",
  created_at: "2026-09-07T00:00:00Z",
};

describe("Schedules page", () => {
  it("lista schedules com cron e estado ativo", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = String(input);
      if (url.includes("/workflows")) {
        return Promise.resolve(
          new Response(JSON.stringify([{ id: "w1", name: "ETL", status: "ACTIVE" }]), {
            status: 200,
          }),
        );
      }
      return Promise.resolve(new Response(JSON.stringify([schedule]), { status: 200 }));
    });

    renderPage();
    await waitFor(() => {
      expect(screen.getByText("*/10 * * * *")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "ativo" })).toBeInTheDocument();
    });
  });

  it("mostra estado vazio", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify([]), { status: 200 }),
    );
    renderPage();
    await waitFor(() =>
      expect(screen.getByText(/Nenhum schedule ainda/)).toBeInTheDocument(),
    );
  });
});
