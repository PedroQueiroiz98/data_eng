import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders } from "@/test/utils";
import { ExecutionDetail } from "@/pages/ExecutionDetail";

vi.mock("@/lib/ws", () => ({ openExecutionSocket: () => () => {} }));

afterEach(() => vi.restoreAllMocks());

const execution = (over: Record<string, unknown>) => ({
  id: "e1",
  notebook_version_id: "v1",
  status: "RUNNING",
  attempt: 1,
  parameters: {},
  created_at: "2026-09-07T00:00:00Z",
  started_at: null,
  finished_at: null,
  duration_ms: null,
  error_code: null,
  error_message: null,
  worker_id: "w1",
  output_notebook_path: null,
  has_output: false,
  ...over,
});

describe("ExecutionDetail ações", () => {
  it("mostra Cancelar para execução RUNNING e chama o endpoint após confirmação", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = String(input);
      if (url.endsWith("/cancel")) {
        return Promise.resolve(
          new Response(JSON.stringify(execution({ status: "CANCELLED" })), { status: 200 }),
        );
      }
      return Promise.resolve(new Response(JSON.stringify(execution({})), { status: 200 }));
    });

    renderWithProviders(<ExecutionDetail />, { route: "/executions/e1", path: "/executions/:id" });

    await userEvent.click(await screen.findByRole("button", { name: /Cancelar/ }));
    // dialog de confirmação
    await userEvent.click(await screen.findByRole("button", { name: /Cancelar execução/ }));

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([u]) => String(u).endsWith("/executions/e1/cancel")),
      ).toBe(true),
    );
  });

  it("mostra Reexecutar para execução FAILED", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify(execution({ status: "FAILED", error_code: "NOTEBOOK_ERROR" })),
        { status: 200 },
      ),
    );
    renderWithProviders(<ExecutionDetail />, { route: "/executions/e1", path: "/executions/:id" });
    expect(await screen.findByRole("button", { name: /Reexecutar/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Cancelar/ })).not.toBeInTheDocument();
  });
});
