import { Link } from "react-router-dom";
import { fmtDuration, isJobTerminal, type Job } from "@/lib/jobs";
import { ActionMenu, StatusChip } from "@/ui";
import { DeleteIcon, ScheduleIcon } from "@/ui/icons";

interface Props {
  job: Job;
  pipelineName: string;
  runNumber?: number;
  onDelete?: (job: Job) => void;
  selected?: boolean;
  onToggleSelect?: (job: Job) => void;
}

const TRIGGER_LABEL: Record<string, string> = {
  MANUAL: "manual",
  SCHEDULED: "agendado",
  API: "api",
};

export function RunCard({
  job,
  pipelineName,
  runNumber,
  onDelete,
  selected,
  onToggleSelect,
}: Props) {
  const hasCounts = job.task_total > 0;
  return (
    <div
      className={`surface relative transition hover:border-primary/40 hover:shadow-e2 ${
        selected ? "border-primary bg-primary/5" : ""
      }`}
    >
      <Link
        to={`/jobs/${job.id}`}
        className={`block py-3 pr-4 ${onToggleSelect ? "pl-11" : "pl-4"}`}
      >
        <div className="flex flex-wrap items-start gap-x-3 gap-y-1">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <span className="truncate font-medium text-fg">{pipelineName}</span>
              {runNumber != null && (
                <span className="whitespace-nowrap text-xs text-fg-faint">Run #{runNumber}</span>
              )}
            </div>
            <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-fg-muted">
              <span className="inline-flex items-center gap-1">
                <ScheduleIcon className="h-3.5 w-3.5" />
                {TRIGGER_LABEL[job.trigger_type] ?? job.trigger_type.toLowerCase()}
              </span>
              <span aria-hidden>·</span>
              <span className="font-mono">{job.id.slice(0, 8)}</span>
            </div>
            <div className="mt-0.5 text-xs text-fg-faint">
              {job.started_at
                ? `Início ${new Date(job.started_at).toLocaleString()}`
                : `Criado ${new Date(job.created_at).toLocaleString()}`}
              {job.finished_at && ` · Fim ${new Date(job.finished_at).toLocaleTimeString()}`}
            </div>
            {hasCounts && (
              <div className="mt-1 text-xs text-fg-muted">
                {job.task_total} jobs ·{" "}
                <span className="text-ok">{job.task_success} success</span> ·{" "}
                <span className={job.task_failed ? "text-danger" : ""}>
                  {job.task_failed} failed
                </span>
                {job.task_running > 0 && (
                  <> · <span className="text-info">{job.task_running} running</span></>
                )}
              </div>
            )}
          </div>
          <div className="flex flex-col items-end gap-1 pr-6">
            <StatusChip status={job.status} />
            <span className="tabular-nums text-xs text-fg-muted">
              {fmtDuration(job.duration_ms)}
            </span>
          </div>
        </div>
      </Link>

      {onToggleSelect && (
        <div
          className="absolute left-3 top-3.5"
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
          }}
        >
          <input
            type="checkbox"
            checked={!!selected}
            onChange={() => onToggleSelect(job)}
            aria-label="Selecionar execução"
          />
        </div>
      )}

      {onDelete && (
        <div
          className="absolute right-1.5 top-1.5"
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
          }}
        >
          <ActionMenu
            items={[
              {
                label: "Excluir execução",
                icon: <DeleteIcon className="h-4 w-4" />,
                danger: true,
                disabled: !isJobTerminal(job.status),
                onClick: () => onDelete(job),
              },
            ]}
          />
        </div>
      )}
    </div>
  );
}
