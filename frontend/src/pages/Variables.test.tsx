import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Variables } from "@/pages/Variables";

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <Variables />
    </QueryClientProvider>,
  );
}

afterEach(() => vi.restoreAllMocks());

describe("Variables page", () => {
  it("lista variáveis com valor visível", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify([
          {
            key: "ENVIRONMENT",
            value: "production",
            scope: "global",
            updated_at: "2026-09-07T00:00:00Z",
          },
        ]),
        { status: 200 },
      ),
    );
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("ENVIRONMENT")).toBeInTheDocument();
      expect(screen.getByText("production")).toBeInTheDocument();
    });
  });
});
