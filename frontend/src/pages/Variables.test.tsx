import { screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders } from "@/test/utils";
import { Variables } from "@/pages/Variables";

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
    renderWithProviders(<Variables />);
    await waitFor(() => {
      expect(screen.getByText("ENVIRONMENT")).toBeInTheDocument();
      expect(screen.getByText("production")).toBeInTheDocument();
    });
  });
});
