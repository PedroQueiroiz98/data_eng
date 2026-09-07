import { screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { JobTaskStatus } from "@/lib/jobs";
import type { JobSocketHandlers } from "@/lib/ws";
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

const task = (name: string, status: JobTaskStatus) => ({
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
});

describe("JobDetail", () => {
  it("renderiza tarefas e timeline do snapshot do WS", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          id: "j1",
          workflow_id: "w1",
          workflow_name: "ETL",
          status: "RUNNING",
          trigger_type: "MANUAL",
          created_at: "2026-09-07T00:00:00Z",
          started_at: null,
          finished_at: null,
          duration_ms: null,
          tasks: [],
          dependencies: [],
        }),
        { status: 200 },
      ),
    );

    renderWithProviders(<JobDetail />, { route: "/jobs/j1", path: "/jobs/:id" });
    await waitFor(() => expect(capturedHandlers).not.toBeNull());

    capturedHandlers!.onSnapshot?.({
      type: "snapshot",
      job: { id: "j1", status: "RUNNING", workflow_name: "ETL" },
      tasks: [task("Extract", "SUCCESS"), task("Load", "RUNNING")],
      logs: [{ seq: 1, ts: "", level: "INFO", message: "job iniciado", job_task_id: null }],
    });

    await waitFor(() => {
      expect(screen.getByText("Extract")).toBeInTheDocument();
      expect(screen.getByText("Load")).toBeInTheDocument();
      expect(screen.getByText("job iniciado")).toBeInTheDocument();
    });
  });
});
