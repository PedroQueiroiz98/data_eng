import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { StatusBadge } from "@/components/StatusBadge";
import { NotebookOutputView } from "@/components/notebook/NotebookOutputView";
import {
  useCancelExecution,
  useExecution,
  useExecutionOutput,
  useRetryExecution,
} from "@/hooks/useExecutions";
import {
  canCancel,
  canRetry,
  isTerminal,
  type ExecutionLog,
  type ExecutionStatus,
} from "@/lib/executions";
import { openExecutionSocket } from "@/lib/ws";

export function ExecutionDetail() {
  const { id = "" } = useParams();
  const cancel = useCancelExecution(id);
  const retry = useRetryExecution(id);

  const [status, setStatus] = useState<ExecutionStatus | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [logs, setLogs] = useState<ExecutionLog[]>([]);
  const [connected, setConnected] = useState(false);
  const [outputReady, setOutputReady] = useState(false);
  const [reopenNonce, setReopenNonce] = useState(0);
  const seenSeq = useRef<Set<number>>(new Set());

  // fallback REST (caso o WS não conecte); pára o polling quando terminal
  const restEnabled = status == null || !isTerminal(status);
  const { data: rest } = useExecution(id, restEnabled);
  const effectiveStatus = status ?? rest?.status ?? null;

  useEffect(() => {
    seenSeq.current = new Set();
    setLogs([]);
    const close = openExecutionSocket(id, {
      onOpen: () => setConnected(true),
      onDisconnect: () => setConnected(false),
      onSnapshot: (e) => {
        setStatus(e.execution.status);
        setErrorMessage(e.execution.error_message);
        if (e.execution.has_output) setOutputReady(true);
        for (const l of e.logs) seenSeq.current.add(l.seq);
        setLogs(e.logs);
      },
      onLog: (l) => {
        if (seenSeq.current.has(l.seq)) return;
        seenSeq.current.add(l.seq);
        setLogs((prev) => [...prev, l]);
      },
      onStatus: (s, msg) => {
        setStatus(s);
        setErrorMessage(msg);
      },
      onOutput: () => setOutputReady(true),
    });
    return close;
  }, [id, reopenNonce]);

  const onRetry = async () => {
    await retry.mutateAsync();
    setStatus("QUEUED");
    setErrorMessage(null);
    setOutputReady(false);
    setReopenNonce((n) => n + 1); // reabre o WS para acompanhar a nova tentativa
  };

  useEffect(() => {
    if (rest?.has_output) setOutputReady(true);
  }, [rest?.has_output]);

  const { data: output } = useExecutionOutput(id, outputReady);

  const params = useMemo(() => rest?.parameters ?? {}, [rest?.parameters]);

  return (
    <div className="mx-auto max-w-4xl">
      <div className="mb-4 flex items-center gap-3">
        <Link to="/executions" className="text-sm text-slate-500 hover:underline">
          ← Executions
        </Link>
        <span className="font-mono text-sm text-slate-500">{id.slice(0, 8)}</span>
        {effectiveStatus && <StatusBadge status={effectiveStatus} />}
        {rest?.attempt ? (
          <span className="text-xs text-slate-400">tentativa #{rest.attempt}</span>
        ) : null}

        <div className="ml-auto flex items-center gap-2">
          {effectiveStatus && canCancel(effectiveStatus) && (
            <button
              type="button"
              onClick={() => cancel.mutate()}
              disabled={cancel.isPending}
              className="rounded border border-slate-300 px-2 py-1 text-xs hover:bg-slate-50 disabled:opacity-40"
            >
              {cancel.isPending ? "Cancelando…" : "Cancelar"}
            </button>
          )}
          {effectiveStatus && canRetry(effectiveStatus) && (
            <button
              type="button"
              onClick={onRetry}
              disabled={retry.isPending}
              className="rounded bg-slate-800 px-2 py-1 text-xs text-white disabled:opacity-40"
            >
              {retry.isPending ? "Refazendo…" : "Refazer"}
            </button>
          )}
          <span className={`text-xs ${connected ? "text-green-600" : "text-slate-400"}`}>
            {connected ? "● ao vivo" : "○ reconectando"}
          </span>
        </div>
      </div>

      {errorMessage && (
        <pre className="mb-4 overflow-x-auto whitespace-pre-wrap rounded border border-red-200 bg-red-50 p-3 text-xs text-red-700">
          {errorMessage}
        </pre>
      )}

      {Object.keys(params).length > 0 && (
        <section className="mb-4">
          <h2 className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-400">
            Parâmetros
          </h2>
          <pre className="overflow-x-auto rounded border border-slate-200 bg-slate-50 p-3 text-xs">
            {JSON.stringify(params, null, 2)}
          </pre>
        </section>
      )}

      <section className="mb-4">
        <h2 className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-400">
          Logs
        </h2>
        <div className="max-h-96 overflow-auto rounded border border-slate-200 bg-slate-900 p-3 font-mono text-xs text-slate-100">
          {logs.length === 0 && <span className="text-slate-500">sem logs ainda…</span>}
          {logs.map((l) => (
            <div key={l.seq} className={l.level === "ERROR" ? "text-red-400" : ""}>
              <span className="text-slate-500">{l.seq.toString().padStart(3, "0")} </span>
              {l.message}
            </div>
          ))}
        </div>
      </section>

      {output && (
        <section>
          <h2 className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-400">
            Notebook executado (output.ipynb)
          </h2>
          <NotebookOutputView notebook={output} />
        </section>
      )}
    </div>
  );
}
