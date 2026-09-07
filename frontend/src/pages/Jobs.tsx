import { Link } from "react-router-dom";
import { useJobs } from "@/hooks/useJobs";
import type { JobStatus } from "@/lib/jobs";

const ICON: Record<JobStatus, string> = {
  QUEUED: "○",
  RUNNING: "◐",
  SUCCESS: "✓",
  FAILED: "✕",
  CANCELLED: "⊘",
};
const COLOR: Record<JobStatus, string> = {
  QUEUED: "text-slate-400",
  RUNNING: "text-blue-600",
  SUCCESS: "text-green-600",
  FAILED: "text-red-600",
  CANCELLED: "text-slate-500",
};

function fmtDuration(ms: number | null): string {
  if (ms == null) return "";
  const s = Math.round(ms / 1000);
  return s < 60 ? `${s}s` : `${Math.floor(s / 60)}m ${s % 60}s`;
}

export function Jobs() {
  const { data, isLoading, isError } = useJobs();

  return (
    <div>
      <h1 className="text-2xl font-semibold">Jobs</h1>
      <section className="mt-5">
        {isLoading && <p className="text-slate-500">Carregando…</p>}
        {isError && <p className="text-red-600">Falha ao carregar jobs.</p>}
        {data && data.length === 0 && (
          <p className="text-slate-500">Nenhum job ainda. Execute um workflow.</p>
        )}
        <ul className="divide-y divide-slate-100 rounded border border-slate-200">
          {data?.map((job) => (
            <li key={job.id}>
              <Link
                to={`/jobs/${job.id}`}
                className="flex items-center gap-3 px-4 py-2.5 hover:bg-slate-50"
              >
                <span className={`text-lg ${COLOR[job.status]}`} aria-hidden>
                  {ICON[job.status]}
                </span>
                <span className="font-mono text-xs text-slate-500">
                  {job.id.slice(0, 8)}
                </span>
                <span className="text-sm text-slate-700">{job.status}</span>
                <span className="ml-auto text-xs text-slate-400">
                  {fmtDuration(job.duration_ms)} ·{" "}
                  {new Date(job.created_at).toLocaleString()}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
