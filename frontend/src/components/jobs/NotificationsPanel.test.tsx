import { screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders } from "@/test/utils";
import { NotificationsPanel } from "@/components/jobs/NotificationsPanel";

afterEach(() => vi.restoreAllMocks());

const rows = [
  {
    id: "n1",
    job_id: "j1",
    execution_id: null,
    channel: "EMAIL",
    event_type: "JOB_FAILED",
    status: "SENT",
    recipient: "pedro@empresa.com",
    attempt: 1,
    max_attempts: 3,
    error_message: null,
    created_at: "2026-09-07T12:06:00Z",
    sent_at: "2026-09-07T12:06:15Z",
    next_retry_at: null,
  },
  {
    id: "n2",
    job_id: "j1",
    execution_id: null,
    channel: "BITRIX",
    event_type: "JOB_FAILED",
    status: "FAILED",
    recipient: "chat3129",
    attempt: 3,
    max_attempts: 3,
    error_message: "Connection timeout",
    created_at: "2026-09-07T12:06:00Z",
    sent_at: null,
    next_retry_at: null,
  },
];

describe("NotificationsPanel", () => {
  it("mostra canais, status e botão de retry para falhas", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(rows), { status: 200 }),
    );
    renderWithProviders(<NotificationsPanel jobId="j1" />);
    await waitFor(() => {
      expect(screen.getByText("EMAIL")).toBeInTheDocument();
      expect(screen.getByText("BITRIX")).toBeInTheDocument();
      expect(screen.getByText("pedro@empresa.com")).toBeInTheDocument();
      expect(screen.getByText("Connection timeout")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /Retry Notification/ })).toBeInTheDocument();
    });
  });

  it("estado vazio quando não há canais", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify([]), { status: 200 }),
    );
    renderWithProviders(<NotificationsPanel jobId="j1" />);
    await waitFor(() =>
      expect(
        screen.getByText(/Nenhum canal de notificação configurado/),
      ).toBeInTheDocument(),
    );
  });
});
