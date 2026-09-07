import { screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders } from "@/test/utils";
import { Dashboard } from "@/pages/Dashboard";

afterEach(() => vi.restoreAllMocks());

function mockApi() {
  vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    const url = String(input);
    if (url.includes("/ready")) {
      return Promise.resolve(
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
          { status: 200 },
        ),
      );
    }
    if (url.includes("/executions")) {
      return Promise.resolve(
        new Response(
          JSON.stringify([
            {
              id: "e1",
              status: "SUCCESS",
              attempt: 1,
              parameters: {},
              created_at: new Date().toISOString(),
              duration_ms: 4000,
              error_code: null,
              notebook_version_id: "v",
              started_at: null,
              finished_at: null,
              error_message: null,
              worker_id: null,
            },
          ]),
          { status: 200 },
        ),
      );
    }
    return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
  });
}

describe("Dashboard", () => {
  it("mostra cards de estatística e serviços", async () => {
    mockApi();
    renderWithProviders(<Dashboard />);
    await waitFor(() => {
      expect(screen.getByText("Sucesso")).toBeInTheDocument();
      expect(screen.getByText("Em execução")).toBeInTheDocument();
      expect(screen.getByText("Últimas execuções")).toBeInTheDocument();
      expect(screen.getByText("postgres")).toBeInTheDocument();
    });
  });
});
