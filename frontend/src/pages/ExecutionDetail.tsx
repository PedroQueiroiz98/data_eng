import { useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { LogTerminal } from "@/components/LogTerminal";
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
import { Button, Card, PageHeader, StatusChip, useConfirm, useToast } from "@/ui";
import { RetryIcon, StopIcon } from "@/ui/icons";

function fmt(iso: string | null | undefined): string {
  return iso ? new Date(iso).toLocaleString() : "—";
}

export function ExecutionDetail() {
  const { id = "" } = useParams();
  const toast = useToast();
  const confirm = useConfirm();
  const cancel = useCancelExecution(id);
  const retry = useRetryExecution(id);

  const [status, setStatus] = useState<ExecutionStatus | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [logs, setLogs] = useState<ExecutionLog[]>([]);
  const [connected, setConnected] = useState(false);
  const [outputReady, setOutputReady] = useState(false);
  const [reopenNonce, setReopenNonce] = useState(0);
  const seenSeq = useRef<Set<number>>(new Set());

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

  useEffect(() => {
    if (rest?.has_output) setOutputReady(true);
  }, [rest?.has_output]);

  const { data: output } = useExecutionOutput(id, outputReady);
  const params = useMemo(() => rest?.parameters ?? {}, [rest?.parameters]);

  const onCancel = async () => {
    if (
      await confirm({
        title: "Cancelar execução",
        message: "Deseja cancelar esta execução?",
        confirmLabel: "Cancelar execução",
        cancelLabel: "Voltar",
        danger: true,
      })
    ) {
      cancel.mutate(undefined, {
        onSuccess: () => toast.success("Cancelamento solicitado"),
        onError: (e) => toast.error((e as Error).message),
      });
    }
  };

  const onRetry = async () => {
    await retry.mutateAsync();
    toast.success("Reexecução enfileirada");
    setStatus("QUEUED");
    setErrorMessage(null);
    setOutputReady(false);
    setReopenNonce((n) => n + 1);
  };

  return (
    <div>
      <PageHeader
        back={{ to: "/executions", label: "Execuções" }}
        title={
          <span className="flex items-center gap-3">
            <span className="font-mono text-lg">{id.slice(0, 8)}</span>
            {effectiveStatus && <StatusChip status={effectiveStatus} />}
          </span>
        }
        subtitle={
          <span className="flex items-center gap-3 text-xs">
            {rest?.attempt ? <span>tentativa #{rest.attempt}</span> : null}
            <span className={connected ? "text-ok" : "text-fg-faint"}>
              {connected ? "● ao vivo" : "○ reconectando"}
            </span>
          </span>
        }
        actions={
          <>
            {effectiveStatus && canCancel(effectiveStatus) && (
              <Button
                variant="outlined"
                size="sm"
                icon={<StopIcon className="h-4 w-4" />}
                loading={cancel.isPending}
                onClick={onCancel}
              >
                Cancelar
              </Button>
            )}
            {effectiveStatus && canRetry(effectiveStatus) && (
              <Button
                size="sm"
                icon={<RetryIcon className="h-4 w-4" />}
                loading={retry.isPending}
                onClick={onRetry}
              >
                Reexecutar
              </Button>
            )}
          </>
        }
      />

      <div className="grid gap-4 sm:grid-cols-3">
        <Card>
          <div className="text-xs uppercase tracking-wide text-fg-faint">Início</div>
          <div className="mt-1 text-sm">{fmt(rest?.started_at)}</div>
        </Card>
        <Card>
          <div className="text-xs uppercase tracking-wide text-fg-faint">Fim</div>
          <div className="mt-1 text-sm">{fmt(rest?.finished_at)}</div>
        </Card>
        <Card>
          <div className="text-xs uppercase tracking-wide text-fg-faint">Duração</div>
          <div className="mt-1 text-sm tabular-nums">
            {rest?.duration_ms != null
              ? `${(rest.duration_ms / 1000).toFixed(1)}s`
              : "—"}
          </div>
        </Card>
      </div>

      {errorMessage && (
        <Card className="mt-4 border-danger/30 bg-danger/10">
          <div className="text-xs font-semibold uppercase tracking-wide text-danger">Erro</div>
          <pre className="mt-1 overflow-x-auto whitespace-pre-wrap text-xs text-danger">
            {errorMessage}
          </pre>
        </Card>
      )}

      {Object.keys(params).length > 0 && (
        <Card className="mt-4">
          <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-fg-faint">
            Parâmetros
          </div>
          <pre className="overflow-x-auto rounded bg-surface-variant p-3 text-xs">
            {JSON.stringify(params, null, 2)}
          </pre>
        </Card>
      )}

      <div className="mt-6">
        <LogTerminal
          lines={logs.map((l) => ({ seq: l.seq, level: l.level, message: l.message }))}
          filename={`execution-${id.slice(0, 8)}.txt`}
        />
      </div>

      {output && (
        <section className="mt-6">
          <h2 className="mb-2 text-sm font-semibold text-fg">
            Notebook executado (output.ipynb)
          </h2>
          <NotebookOutputView notebook={output} />
        </section>
      )}
    </div>
  );
}
