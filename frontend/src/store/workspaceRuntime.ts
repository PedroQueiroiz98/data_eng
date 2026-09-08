import { create } from "zustand";
import type { KernelEvent, KernelStatus } from "@/lib/kernels";

type RunState = "running" | "ok" | "error";

export interface TimelineEntry {
  cellId: string;
  status: RunState;
  durationMs?: number;
  at: number;
}

export interface RuntimeLogLine {
  seq: number;
  text: string;
  level: "info" | "error";
}

interface RuntimeState {
  kernelStatus: KernelStatus;
  connected: boolean;
  timeline: TimelineEntry[];
  logLines: RuntimeLogLine[];
  runningSince: number | null;

  ingest: (e: KernelEvent) => void;
  setKernel: (status: KernelStatus, connected: boolean) => void;
  clear: () => void;
}

let seqCounter = 0;

export const useWorkspaceRuntime = create<RuntimeState>((set) => ({
  kernelStatus: "starting",
  connected: false,
  timeline: [],
  logLines: [],
  runningSince: null,

  setKernel: (status, connected) => set({ kernelStatus: status, connected }),

  clear: () => set({ timeline: [], logLines: [], runningSince: null }),

  ingest: (e) =>
    set((s) => {
      if (e.type === "kernel.status" && e.status) {
        return { kernelStatus: e.status as KernelStatus };
      }
      if (e.type === "cell.started" && e.cell_id) {
        const entry: TimelineEntry = {
          cellId: e.cell_id,
          status: "running",
          at: Date.now(),
        };
        return {
          runningSince: s.runningSince ?? Date.now(),
          timeline: [
            ...s.timeline.filter((t) => t.cellId !== e.cell_id),
            entry,
          ].slice(-200),
        };
      }
      if ((e.type === "cell.output" || e.type === "cell.error") && e.output) {
        const out = e.output;
        let text = "";
        if (out.output_type === "stream") {
          text = Array.isArray(out.text) ? out.text.join("") : out.text ?? "";
        } else if (out.output_type === "error") {
          text = (out.traceback ?? []).join("\n") || `${out.ename}: ${out.evalue}`;
        } else {
          const plain = out.data?.["text/plain"];
          text = Array.isArray(plain) ? plain.join("") : (plain as string) ?? "";
        }
        if (!text) return {};
        const line: RuntimeLogLine = {
          seq: ++seqCounter,
          text,
          level: e.type === "cell.error" ? "error" : "info",
        };
        return { logLines: [...s.logLines, line].slice(-2000) };
      }
      if (e.type === "cell.finished" && e.cell_id) {
        const status: RunState = e.status === "error" ? "error" : "ok";
        const stillRunning = s.timeline.some(
          (t) => t.cellId !== e.cell_id && t.status === "running",
        );
        return {
          runningSince: stillRunning ? s.runningSince : null,
          timeline: s.timeline.map((t) =>
            t.cellId === e.cell_id
              ? { ...t, status, durationMs: e.duration_ms }
              : t,
          ),
        };
      }
      return {};
    }),
}));
