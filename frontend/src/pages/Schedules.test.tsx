import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders } from "@/test/utils";
import { Schedules } from "@/pages/Schedules";

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

function mockApi(schedules: unknown[]) {
  vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    const url = String(input);
    if (url.includes("/workflows")) {
      return Promise.resolve(
        new Response(JSON.stringify([{ id: "w1", name: "ETL", status: "ACTIVE" }]), {
          status: 200,
        }),
      );
    }
    return Promise.resolve(new Response(JSON.stringify(schedules), { status: 200 }));
  });
}

describe("Schedules page", () => {
  it("tem alternância Calendário/Lista e mostra o agendamento na lista", async () => {
    mockApi([schedule]);
    renderWithProviders(<Schedules />);

    // aba padrão = calendário
    expect(await screen.findByRole("button", { name: /Calendário/ })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /^Lista$/ }));

    await waitFor(() => {
      expect(screen.getByText("*/10 * * * *", { exact: false })).toBeInTheDocument();
      expect(screen.getByText(/A cada 10 min/)).toBeInTheDocument();
    });
  });

  it("mostra estado vazio", async () => {
    mockApi([]);
    renderWithProviders(<Schedules />);
    await waitFor(() =>
      expect(screen.getByText(/Nenhum agendamento/)).toBeInTheDocument(),
    );
  });
});
