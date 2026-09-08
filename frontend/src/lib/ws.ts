import {
  isTerminal,
  type ExecutionDetail,
  type ExecutionLog,
  type ExecutionStatus,
} from "@/lib/executions";
import {
  isJobTerminal,
  type JobDetail,
  type JobLog,
  type JobStatus,
  type JobTask,
} from "@/lib/jobs";
import type { KernelEvent, KernelStatus } from "@/lib/kernels";
import { getAuthToken } from "@/lib/api";

const tokenParam = (): string => {
  const t = getAuthToken();
  return t ? `&token=${encodeURIComponent(t)}` : "";
};

export interface SnapshotEvent {
  type: "snapshot";
  execution: ExecutionDetail;
  logs: ExecutionLog[];
}

export interface LogEvent {
  type: "log";
  seq: number;
  level: ExecutionLog["level"];
  message: string;
  ts: string;
  attempt: number;
}

export interface StatusEvent {
  type: "status_changed";
  status: ExecutionStatus;
  error_message?: string | null;
}

export interface OutputEvent {
  type: "output";
  available: boolean;
}

export type ExecutionEvent = SnapshotEvent | LogEvent | StatusEvent | OutputEvent | { type: string };

export interface ExecutionSocketHandlers {
  onSnapshot?: (e: SnapshotEvent) => void;
  onLog?: (e: LogEvent) => void;
  onStatus?: (status: ExecutionStatus, errorMessage: string | null) => void;
  onOutput?: () => void;
  onOpen?: () => void;
  onDisconnect?: () => void;
}

export interface ExecutionSocketDeps {
  WebSocketImpl?: typeof WebSocket;
  baseUrl?: string;
  maxDelayMs?: number;
}

function wsUrl(executionId: string, afterSeq: number, baseUrl: string): string {
  if (baseUrl.startsWith("ws://") || baseUrl.startsWith("wss://")) {
    return `${baseUrl}/executions/${executionId}?after_seq=${afterSeq}${tokenParam()}`;
  }
  const proto =
    typeof location !== "undefined" && location.protocol === "https:" ? "wss" : "ws";
  const host = typeof location !== "undefined" ? location.host : "localhost";
  return `${proto}://${host}${baseUrl}/executions/${executionId}?after_seq=${afterSeq}${tokenParam()}`;
}

/**
 * Abre um WebSocket para a execução, com reconexão automática e backoff.
 * Ao reconectar, retoma a partir do último `seq` de log recebido (`after_seq`).
 * Retorna uma função para encerrar.
 */
export function openExecutionSocket(
  executionId: string,
  handlers: ExecutionSocketHandlers,
  deps: ExecutionSocketDeps = {},
): () => void {
  const WS = deps.WebSocketImpl ?? WebSocket;
  const baseUrl = deps.baseUrl ?? import.meta.env.VITE_WS_BASE_URL ?? "/ws";
  const maxDelay = deps.maxDelayMs ?? 15_000;

  let socket: WebSocket | null = null;
  let stopped = false;
  let lastSeq = 0;
  let attempt = 0;
  let timer: ReturnType<typeof setTimeout> | undefined;

  const stop = (): void => {
    stopped = true;
    if (timer) clearTimeout(timer);
    socket?.close();
  };

  const scheduleReconnect = (): void => {
    if (stopped) return;
    attempt += 1;
    const delay = Math.min(1000 * 2 ** attempt, maxDelay);
    timer = setTimeout(connect, delay);
  };

  function connect(): void {
    if (stopped) return;
    socket = new WS(wsUrl(executionId, lastSeq, baseUrl));

    socket.onopen = () => {
      attempt = 0;
      handlers.onOpen?.();
    };

    socket.onmessage = (ev: MessageEvent) => {
      let evt: ExecutionEvent;
      try {
        evt = JSON.parse(ev.data as string) as ExecutionEvent;
      } catch {
        return;
      }
      if (evt.type === "snapshot") {
        const s = evt as SnapshotEvent;
        for (const l of s.logs) lastSeq = Math.max(lastSeq, l.seq);
        handlers.onSnapshot?.(s);
        if (isTerminal(s.execution.status)) stop();
      } else if (evt.type === "log") {
        const l = evt as LogEvent;
        lastSeq = Math.max(lastSeq, l.seq);
        handlers.onLog?.(l);
      } else if (evt.type === "status_changed") {
        const st = evt as StatusEvent;
        handlers.onStatus?.(st.status, st.error_message ?? null);
        if (isTerminal(st.status)) stop();
      } else if (evt.type === "output") {
        handlers.onOutput?.();
      }
    };

    socket.onclose = () => {
      if (stopped) return;
      handlers.onDisconnect?.();
      scheduleReconnect();
    };

    socket.onerror = () => socket?.close();
  }

  connect();
  return stop;
}

// ─── Kernel socket ───────────────────────────────────────────────────────────

export interface KernelSnapshot {
  type: "snapshot";
  session: {
    session_id: string;
    status: KernelStatus;
    execution_count: number;
    notebook_path: string;
  };
  events: KernelEvent[];
}

export interface KernelSocketHandlers {
  onSnapshot?: (e: KernelSnapshot) => void;
  onEvent?: (e: KernelEvent) => void;
  onOpen?: () => void;
  onDisconnect?: () => void;
}

export function openKernelSocket(
  sessionId: string,
  handlers: KernelSocketHandlers,
  deps: ExecutionSocketDeps = {},
): () => void {
  const WS = deps.WebSocketImpl ?? WebSocket;
  const baseUrl = deps.baseUrl ?? import.meta.env.VITE_WS_BASE_URL ?? "/ws";
  const maxDelay = deps.maxDelayMs ?? 15_000;

  let socket: WebSocket | null = null;
  let stopped = false;
  let lastSeq = 0;
  let attempt = 0;
  let timer: ReturnType<typeof setTimeout> | undefined;

  const stop = (): void => {
    stopped = true;
    if (timer) clearTimeout(timer);
    socket?.close();
  };

  function url(): string {
    const proto =
      typeof location !== "undefined" && location.protocol === "https:" ? "wss" : "ws";
    const host = typeof location !== "undefined" ? location.host : "localhost";
    const prefix = baseUrl.startsWith("ws") ? baseUrl : `${proto}://${host}${baseUrl}`;
    return `${prefix}/kernels/${sessionId}?after_seq=${lastSeq}${tokenParam()}`;
  }

  function connect(): void {
    if (stopped) return;
    socket = new WS(url());
    socket.onopen = () => {
      attempt = 0;
      handlers.onOpen?.();
    };
    socket.onmessage = (ev: MessageEvent) => {
      let evt: KernelEvent | KernelSnapshot;
      try {
        evt = JSON.parse(ev.data as string) as KernelEvent | KernelSnapshot;
      } catch {
        return;
      }
      if (evt.type === "snapshot") {
        const s = evt as KernelSnapshot;
        for (const e of s.events) if (e.seq) lastSeq = Math.max(lastSeq, e.seq);
        handlers.onSnapshot?.(s);
      } else {
        const e = evt as KernelEvent;
        if (e.seq) lastSeq = Math.max(lastSeq, e.seq);
        handlers.onEvent?.(e);
      }
    };
    socket.onclose = () => {
      if (stopped) return;
      handlers.onDisconnect?.();
      attempt += 1;
      timer = setTimeout(connect, Math.min(1000 * 2 ** attempt, maxDelay));
    };
    socket.onerror = () => socket?.close();
  }

  connect();
  return stop;
}

// ─── Job socket ──────────────────────────────────────────────────────────────

export interface JobSnapshotEvent {
  type: "snapshot";
  job: Omit<JobDetail, "tasks">;
  tasks: JobTask[];
  logs: JobLog[];
}

export interface JobSocketHandlers {
  onSnapshot?: (e: JobSnapshotEvent) => void;
  onLog?: (e: { seq: number; message: string; job_task_id: string | null }) => void;
  onStatus?: (status: JobStatus) => void;
  onProgress?: () => void;
  onOpen?: () => void;
  onDisconnect?: () => void;
}

export function openJobSocket(
  jobId: string,
  handlers: JobSocketHandlers,
  deps: ExecutionSocketDeps = {},
): () => void {
  const WS = deps.WebSocketImpl ?? WebSocket;
  const baseUrl = deps.baseUrl ?? import.meta.env.VITE_WS_BASE_URL ?? "/ws";
  const maxDelay = deps.maxDelayMs ?? 15_000;

  let socket: WebSocket | null = null;
  let stopped = false;
  let lastSeq = 0;
  let attempt = 0;
  let timer: ReturnType<typeof setTimeout> | undefined;

  const stop = (): void => {
    stopped = true;
    if (timer) clearTimeout(timer);
    socket?.close();
  };

  function connect(): void {
    if (stopped) return;
    const url = baseUrl.startsWith("ws")
      ? `${baseUrl}/jobs/${jobId}?after_seq=${lastSeq}${tokenParam()}`
      : `${typeof location !== "undefined" && location.protocol === "https:" ? "wss" : "ws"}://${
          typeof location !== "undefined" ? location.host : "localhost"
        }${baseUrl}/jobs/${jobId}?after_seq=${lastSeq}${tokenParam()}`;
    socket = new WS(url);

    socket.onopen = () => {
      attempt = 0;
      handlers.onOpen?.();
    };
    socket.onmessage = (ev: MessageEvent) => {
      let evt: { type: string; [k: string]: unknown };
      try {
        evt = JSON.parse(ev.data as string);
      } catch {
        return;
      }
      if (evt.type === "snapshot") {
        const s = evt as unknown as JobSnapshotEvent;
        for (const l of s.logs) lastSeq = Math.max(lastSeq, l.seq);
        handlers.onSnapshot?.(s);
        if (isJobTerminal(s.job.status)) stop();
      } else if (evt.type === "log") {
        const seq = Number(evt.seq);
        lastSeq = Math.max(lastSeq, seq);
        handlers.onLog?.({
          seq,
          message: String(evt.message),
          job_task_id: (evt.job_task_id as string | null) ?? null,
        });
      } else if (evt.type === "status_changed") {
        const st = String(evt.status) as JobStatus;
        handlers.onStatus?.(st);
        if (isJobTerminal(st)) stop();
      } else if (evt.type === "progress") {
        handlers.onProgress?.();
      }
    };
    socket.onclose = () => {
      if (stopped) return;
      handlers.onDisconnect?.();
      attempt += 1;
      timer = setTimeout(connect, Math.min(1000 * 2 ** attempt, maxDelay));
    };
    socket.onerror = () => socket?.close();
  }

  connect();
  return stop;
}
