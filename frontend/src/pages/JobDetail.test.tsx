import { screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { JobTask, JobTaskStatus } from "@/lib/jobs";
import type { JobSnapshotEvent, JobSocketHandlers } from "@/lib/ws";
import { renderWithProviders } from "@/test/utils";
import { JobDetail } from "@/pages/JobDetail";

let capturedHandlers: JobSocketHandlers | null = null;
vi.mock("@/lib/ws", () => ({
  openJobSocket: (_id: string, handlers: JobSocketHandlers) => {
    capturedHandlers = handlers;
    return () => {};
  },
}));

afterEach(() => {
  vi.restoreAllMocks();
  capturedHandlers = null;
});

const task = (name: string, status: JobTaskStatus): JobTask => ({
  id: `t-${name}`,
  workflow_task_id: `w-${name}`,
  execution_id: null,
  status,
  attempt: 1,
  started_at: null,
  finished_at: null,
  duration_ms: null,
  error_message: null,
  name,
  notebook_id: null,
  notebook_name: "",
});

const restJob = {
  id: "j1",
  workflow_id: "w1",
  workflow_name: "ETL",
  status: "RUNNING",
  trigger_type: "MANUAL",
  created_at: "2026-09-07T00:00:00Z",
  started_at: "2026-09-07T00:00:00Z",
  finished_at: null,
  duration_ms: null,
  task_total: 2,
  task_success: 1,
  task_failed: 0,
  task_running: 1,
  started_by: "pedro@x.com",
  parameters: { date: "2026-09-07", api_key: "********" },
  tasks: [],
  dependencies: [],
};

const snapshot = (): JobSnapshotEvent => ({
  type: "snapshot",
  job: { ...restJob } as unknown as JobSnapshotEvent["job"],
  tasks: [task("Extract", "SUCCESS"), task("Load", "RUNNING")],
  logs: [{ seq: 1, ts: "", level: "INFO", message: "job iniciado", job_task_id: null }],
});

describe("JobDetail", () => {
  it("renderiza resumo, timeline e console a partir do snapshot do WS", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = String(input);
      const body = url.includes("/jobs/j1") && !url.includes("workflow_id") ? restJob : [restJob];
      return Promise.resolve(new Response(JSON.stringify(body), { status: 200 }));
    });

    renderWithProviders(<JobDetail />, { route: "/jobs/j1", path: "/jobs/:id" });
    await waitFor(() => expect(capturedHandlers).not.toBeNull());

    capturedHandlers!.onSnapshot?.(snapshot());

    await waitFor(() => {
      expect(screen.getByText("Extract")).toBeInTheDocument();
      // "Load" aparece na timeline e no painel de detalhe (tarefa RUNNING selecionada)
      expect(screen.getAllByText("Load").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText(/job iniciado/).length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText("RUNNING")).toBeInTheDocument();
      expect(screen.getByText("pedro@x.com")).toBeInTheDocument();
    });
  });

  it("mostra parâmetros com segredo mascarado na aba Parâmetros", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = String(input);
      const body = url.includes("/jobs/j1") && !url.includes("workflow_id") ? restJob : [restJob];
      return Promise.resolve(new Response(JSON.stringify(body), { status: 200 }));
    });

    renderWithProviders(<JobDetail />, { route: "/jobs/j1", path: "/jobs/:id" });
    await waitFor(() => expect(capturedHandlers).not.toBeNull());
    capturedHandlers!.onSnapshot?.(snapshot());

    await screen.findByText("Extract");
    screen.getByRole("tab", { name: /Parâmetros/ }).click();
    await waitFor(() => {
      expect(screen.getAllByText(/api_key/).length).toBeGreaterThan(0);
      expect(screen.getAllByText(/= \*{8}/).length).toBeGreaterThan(0);
    });
  });
});
