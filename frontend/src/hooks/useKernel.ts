import { useCallback, useEffect, useRef, useState } from "react";
import {
  executeCell,
  interruptKernel,
  openKernelSession,
  restartKernel,
  type KernelEvent,
  type KernelStatus,
} from "@/lib/kernels";
import { openKernelSocket } from "@/lib/ws";

export interface UseKernel {
  status: KernelStatus;
  connected: boolean;
  executionCount: number;
  /** id da sessão de kernel (null enquanto não abriu) */
  sessionId: string | null;
  runCell: (cellId: string, code: string) => Promise<"ok" | "error">;
  interrupt: () => void;
  restart: () => void;
}

/**
 * Abre (ou reusa) a sessão de kernel para `workspaceId + notebookPath` e conecta
 * o WebSocket. Todo evento de célula é repassado a `onEvent` (o editor atualiza o
 * reducer). `runCell` resolve quando chega o `cell.finished` correspondente.
 */
export function useKernel(
  workspaceId: string,
  notebookPath: string,
  onEvent: (e: KernelEvent) => void,
): UseKernel {
  const [status, setStatus] = useState<KernelStatus>("starting");
  const [connected, setConnected] = useState(false);
  const [executionCount, setExecutionCount] = useState(0);
  const [sessionIdState, setSessionIdState] = useState<string | null>(null);
  const sessionId = useRef<string | null>(null);
  const pending = useRef(new Map<string, (r: "ok" | "error") => void>());
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  useEffect(() => {
    let cancelled = false;
    let close: (() => void) | undefined;

    const handle = (e: KernelEvent): void => {
      if (e.type === "kernel.status" && e.status) {
        setStatus(e.status as KernelStatus);
      }
      if (e.type === "cell.finished") {
        if (typeof e.execution_count === "number") setExecutionCount(e.execution_count);
        if (e.cell_id) {
          const resolve = pending.current.get(e.cell_id);
          if (resolve) {
            pending.current.delete(e.cell_id);
            resolve(e.status === "error" ? "error" : "ok");
          }
        }
      }
      onEventRef.current(e);
    };

    openKernelSession(workspaceId, notebookPath)
      .then((s) => {
        if (cancelled) return;
        sessionId.current = s.session_id;
        setSessionIdState(s.session_id);
        setStatus(s.status);
        setExecutionCount(s.execution_count);
        close = openKernelSocket(s.session_id, {
          onOpen: () => setConnected(true),
          onDisconnect: () => setConnected(false),
          onSnapshot: (snap) => {
            setStatus(snap.session.status);
            setExecutionCount(snap.session.execution_count);
            snap.events.forEach(handle);
          },
          onEvent: handle,
        });
      })
      .catch(() => setStatus("dead"));

    return () => {
      cancelled = true;
      close?.();
      pending.current.forEach((r) => r("error"));
      pending.current.clear();
      setSessionIdState(null);
    };
  }, [workspaceId, notebookPath]);

  const runCell = useCallback(
    (cellId: string, code: string): Promise<"ok" | "error"> => {
      const sid = sessionId.current;
      if (!sid) return Promise.resolve("error");
      return new Promise((resolve) => {
        pending.current.set(cellId, resolve);
        executeCell(workspaceId, sid, cellId, code).catch(() => {
          pending.current.delete(cellId);
          resolve("error");
        });
      });
    },
    [workspaceId],
  );

  const interrupt = useCallback(() => {
    if (sessionId.current) void interruptKernel(workspaceId, sessionId.current);
  }, [workspaceId]);

  const restart = useCallback(() => {
    if (sessionId.current) void restartKernel(workspaceId, sessionId.current);
  }, [workspaceId]);

  return {
    status,
    connected,
    executionCount,
    sessionId: sessionIdState,
    runCell,
    interrupt,
    restart,
  };
}
