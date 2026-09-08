import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders } from "@/test/utils";
import { NotificationDeliveryHistory } from "@/components/notifications/NotificationDeliveryHistory";

afterEach(() => vi.restoreAllMocks());

const DELIVERY = {
  id: "d1",
  notification_provider_id: "p1",
  provider_type: "EMAIL",
  event_type: "JOB_FAILED",
  workflow_id: null,
  job_id: "job-abcdef12",
  execution_id: null,
  status: "FAILED",
  attempt: 3,
  max_attempts: 3,
  error_message: "Connection timeout",
  recipient: "a@x.com",
  created_at: "2026-09-07T14:32:00Z",
  sent_at: null,
  next_retry_at: null,
};

function mockFetch(onRetry?: () => void) {
  return vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    const url = String(input);
    if (url.includes("/notifications/providers")) {
      return Promise.resolve(
        new Response(JSON.stringify([{ id: "p1", name: "E-mail Ops" }]), { status: 200 }),
      );
    }
    if (url.includes("/deliveries/d1/retry")) {
      onRetry?.();
      return Promise.resolve(new Response(JSON.stringify({ status: "queued" }), { status: 202 }));
    }
    if (url.includes("/notifications/deliveries")) {
      return Promise.resolve(
        new Response(
          JSON.stringify({ items: [DELIVERY], total: 1, limit: 100, offset: 0 }),
          { status: 200 },
        ),
      );
    }
    return Promise.resolve(new Response("[]", { status: 200 }));
  });
}

describe("NotificationDeliveryHistory", () => {
  it("mostra a entrega e permite reenviar quando FAILED", async () => {
    const retry = vi.fn();
    mockFetch(retry);
    renderWithProviders(<NotificationDeliveryHistory />);

    expect(await screen.findByText("Connection timeout")).toBeInTheDocument();
    await userEvent.click(screen.getByText("Connection timeout"));

    const drawer = await screen.findByRole("dialog");
    await userEvent.click(within(drawer).getByRole("button", { name: "Reenviar" }));
    await waitFor(() => expect(retry).toHaveBeenCalled());
  });

  it("no modo compact não renderiza a barra de filtros", async () => {
    mockFetch();
    renderWithProviders(<NotificationDeliveryHistory jobFilter="job-1" compact />);
    await screen.findByText("Connection timeout");
    expect(screen.queryByLabelText("Ambiente")).not.toBeInTheDocument();
  });

  it("filtra por status e monta a query", async () => {
    const fetchSpy = mockFetch();
    renderWithProviders(<NotificationDeliveryHistory />);
    await screen.findByText("Connection timeout");

    await userEvent.selectOptions(screen.getByLabelText("Status"), "FAILED");
    await waitFor(() => {
      const called = fetchSpy.mock.calls.some((c) =>
        String(c[0]).includes("status=FAILED"),
      );
      expect(called).toBe(true);
    });
  });
});
