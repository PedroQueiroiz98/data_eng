import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { fmtDuration, type JobTask } from "@/lib/jobs";
import { Button, StatusChip } from "@/ui";
import { DownloadIcon, RetryIcon, ViewIcon } from "@/ui/icons";

interface Props {
  task: JobTask;
  parameters: Record<string, unknown>;
  canRetry: boolean;
  retrying?: boolean;
  onRetry?: () => void;
  runningStep?: string;
  elapsedLabel?: string;
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex justify-between gap-4 py-1.5 text-sm">
      <span className="shrink-0 text-fg-faint">{label}</span>
      <span className="min-w-0 truncate text-right text-fg">{children}</span>
    </div>
  );
}

export function TaskDetailPanel({
  task,
  parameters,
  canRetry,
  retrying,
  onRetry,
  runningStep,
  elapsedLabel,
}: Props) {
  const paramEntries = Object.entries(parameters);
  const failed = task.status === "FAILED";
  const running = task.status === "RUNNING";

  return (
    <div className="surface flex flex-col divide-y divide-surface-border">
      <div className="flex items-center gap-2 px-4 py-3">
        <span className="min-w-0 flex-1 truncate font-medium text-fg">{task.name}</span>
        <StatusChip status={task.status} size="sm" />
      </div>

      {running && (
        <div className="px-4 py-3">
          <div className="flex items-center justify-between text-xs text-info">
            <span>RUNNING{elapsedLabel ? ` · ${elapsedLabel}` : ""}</span>
            {runningStep && <span>{runningStep}</span>}
          </div>
          <div className="mt-1 h-1.5 overflow-hidden rounded bg-info/20">
            <div className="h-full w-full origin-left animate-indeterminate rounded bg-info" />
          </div>
        </div>
      )}

      {failed && (
        <div className="bg-danger/5 px-4 py-3">
          <div className="text-xs font-semibold uppercase tracking-wide text-danger">Falha</div>
          <pre className="mt-1 overflow-x-auto whitespace-pre-wrap text-xs text-danger">
            {task.error_message || "erro sem detalhe"}
          </pre>
          <div className="mt-1 text-xs text-fg-muted">Tentativa {task.attempt}</div>
        </div>
      )}

      <div className="px-4 py-2">
        <Row label="Duração">{fmtDuration(task.duration_ms)}</Row>
        <Row label="Início">{task.started_at ? new Date(task.started_at).toLocaleString() : "—"}</Row>
        <Row label="Término">
          {task.finished_at ? new Date(task.finished_at).toLocaleString() : "—"}
        </Row>
        <Row label="Tentativa">{task.attempt || 1}</Row>
        <Row label="Notebook">
          {task.notebook_name || task.notebook_id?.slice(0, 8) || "—"}
        </Row>
        {task.execution_id && (
          <Row label="Execução">
            <span className="font-mono text-xs">{task.execution_id.slice(0, 8)}</span>
          </Row>
        )}
      </div>

      {paramEntries.length > 0 && (
        <div className="px-4 py-3">
          <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-fg-faint">
            Parâmetros
          </div>
          <dl className="space-y-0.5 font-mono text-xs">
            {paramEntries.map(([k, v]) => (
              <div key={k} className="flex gap-2">
                <dt className="text-fg-muted">{k}</dt>
                <dd className="min-w-0 truncate text-fg">= {String(v)}</dd>
              </div>
            ))}
          </dl>
        </div>
      )}

      {task.execution_id && (
        <div className="px-4 py-3">
          <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-fg-faint">
            Artifacts
          </div>
          <div className="flex flex-col gap-1 text-sm">
            <Link
              to={`/executions/${task.execution_id}`}
              className="inline-flex items-center gap-1.5 text-primary hover:underline"
            >
              <ViewIcon className="h-3.5 w-3.5" /> output.ipynb (notebook executado)
            </Link>
            <Link
              to={`/executions/${task.execution_id}`}
              className="inline-flex items-center gap-1.5 text-primary hover:underline"
            >
              <DownloadIcon className="h-3.5 w-3.5" /> logs da execução
            </Link>
          </div>
        </div>
      )}

      {(task.execution_id || (canRetry && onRetry)) && (
        <div className="flex items-center gap-2 px-4 py-3">
          {task.execution_id && (
            <Link
              to={`/executions/${task.execution_id}`}
              className="inline-flex h-8 items-center gap-1.5 rounded-md border border-surface-border bg-surface px-3 text-xs font-medium text-fg hover:bg-surface-variant"
            >
              <ViewIcon className="h-4 w-4" /> Ver logs
            </Link>
          )}
          {canRetry && onRetry && (
            <Button
              size="sm"
              icon={<RetryIcon className="h-4 w-4" />}
              loading={retrying}
              onClick={onRetry}
            >
              Retry
            </Button>
          )}
        </div>
      )}
    </div>
  );
}
