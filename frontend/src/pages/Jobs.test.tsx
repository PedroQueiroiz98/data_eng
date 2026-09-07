import { screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders } from "@/test/utils";
import { Jobs } from "@/pages/Jobs";

afterEach(() => vi.restoreAllMocks());

const job = {
  id: "job12345-0000-0000-0000-000000000000",
  workflow_id: "w1",
  status: "SUCCESS",
  trigger_type: "MANUAL",
  created_at: "2026-09-07T00:00:00Z",
  started_at: "2026-09-07T00:00:00Z",
  finished_at: "2026-09-07T00:02:31Z",
  duration_ms: 151000,
  task_total: 6,
  task_success: 6,
  task_failed: 0,
  task_running: 0,
};

function mockFetch(jobs: unknown[], workflows: unknown[] = [{ id: "w1", name: "Customer ETL" }]) {
  vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    const url = String(input);
    const body = url.includes("/workflows") ? workflows : jobs;
    return Promise.resolve(new Response(JSON.stringify(body), { status: 200 }));
  });
}

describe("Jobs page", () => {
  it("mostra o card de run com pipeline, status, duração e contagem de jobs", async () => {
    mockFetch([job]);
    renderWithProviders(<Jobs />);
    await waitFor(() => {
      expect(screen.getByText("Customer ETL")).toBeInTheDocument();
      expect(screen.getByText("Success")).toBeInTheDocument();
      expect(screen.getByText(/2m 31s/)).toBeInTheDocument();
      expect(screen.getByText(/6 jobs/)).toBeInTheDocument();
      expect(screen.getByText("Run #1")).toBeInTheDocument();
    });
  });

  it("mostra estado vazio", async () => {
    mockFetch([]);
    renderWithProviders(<Jobs />);
    await waitFor(() =>
      expect(screen.getByText(/Nenhuma execução ainda/)).toBeInTheDocument(),
    );
  });
});
