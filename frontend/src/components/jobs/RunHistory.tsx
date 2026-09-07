import { Link } from "react-router-dom";
import { fmtDuration, type Job } from "@/lib/jobs";
import { StatusIcon } from "@/ui";

interface Props {
  jobs: Job[]; // do mesmo workflow, mais recentes primeiro
  currentId: string;
  /** número de run por id (mesma ordem cronológica do workflow) */
  runNumberById: Map<string, number>;
}

export function RunHistory({ jobs, currentId, runNumberById }: Props) {
  if (jobs.length <= 1) {
    return <p className="px-4 py-6 text-sm text-fg-faint">Sem execuções anteriores.</p>;
  }
  return (
    <ul className="divide-y divide-surface-border text-sm">
      {jobs.map((j) => {
        const current = j.id === currentId;
        return (
          <li key={j.id}>
            <Link
              to={`/jobs/${j.id}`}
              className={`flex items-center gap-3 px-4 py-2.5 hover:bg-surface-variant ${
                current ? "bg-primary/10" : ""
              }`}
            >
              <StatusIcon status={j.status} className="h-4 w-4 shrink-0" />
              <span className="w-16 font-mono text-xs text-fg-muted">
                #{runNumberById.get(j.id) ?? "—"}
              </span>
              <span className="text-fg">{j.status}</span>
              <span className="ml-auto tabular-nums text-xs text-fg-faint">
                {fmtDuration(j.duration_ms)} · {new Date(j.created_at).toLocaleDateString()}
              </span>
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
