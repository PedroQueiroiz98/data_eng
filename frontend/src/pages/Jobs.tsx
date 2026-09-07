import { useMemo, useState } from "react";
import { RunCard } from "@/components/jobs/RunCard";
import { useJobs } from "@/hooks/useJobs";
import { useWorkflows } from "@/hooks/useWorkflows";
import type { Job, JobStatus } from "@/lib/jobs";
import { EmptyState, PageHeader, Skeleton } from "@/ui";
import { JobsIcon, SearchIcon } from "@/ui/icons";

const STATUS_FILTERS: (JobStatus | "ALL")[] = [
  "ALL",
  "RUNNING",
  "QUEUED",
  "SUCCESS",
  "FAILED",
  "CANCELLED",
];

/** Números de run por pipeline: 1 = job mais antigo do workflow. */
function runNumbers(jobs: Job[]): Map<string, number> {
  const byWf = new Map<string, Job[]>();
  for (const j of jobs) {
    const arr = byWf.get(j.workflow_id) ?? [];
    arr.push(j);
    byWf.set(j.workflow_id, arr);
  }
  const out = new Map<string, number>();
  for (const arr of byWf.values()) {
    arr
      .slice()
      .sort((a, b) => a.created_at.localeCompare(b.created_at))
      .forEach((j, i) => out.set(j.id, i + 1));
  }
  return out;
}

export function Jobs() {
  const { data, isLoading, isError } = useJobs();
  const { data: workflows } = useWorkflows();
  const [status, setStatus] = useState<(typeof STATUS_FILTERS)[number]>("ALL");
  const [query, setQuery] = useState("");

  const wfName = useMemo(() => {
    const m = new Map<string, string>();
    for (const w of workflows ?? []) m.set(w.id, w.name);
    return m;
  }, [workflows]);

  const runNo = useMemo(() => runNumbers(data ?? []), [data]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (data ?? []).filter((j) => {
      if (status !== "ALL" && j.status !== status) return false;
      if (!q) return true;
      const name = (wfName.get(j.workflow_id) ?? "").toLowerCase();
      return name.includes(q) || j.id.toLowerCase().includes(q);
    });
  }, [data, status, query, wfName]);

  return (
    <div>
      <PageHeader title="Execuções" subtitle="Runs de pipelines (workflows)." />

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <div className="flex items-center gap-0.5 rounded-md border border-surface-border p-0.5">
          {STATUS_FILTERS.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => setStatus(s)}
              className={`rounded px-2.5 py-1 text-xs transition ${
                status === s
                  ? "bg-primary text-primary-fg"
                  : "text-fg-muted hover:bg-surface-variant"
              }`}
            >
              {s === "ALL" ? "Todas" : s}
            </button>
          ))}
        </div>
        <div className="relative ml-auto">
          <SearchIcon className="pointer-events-none absolute left-2 top-1/2 h-4 w-4 -translate-y-1/2 text-fg-faint" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Pesquisar pipeline ou id"
            className="w-56 rounded-md border border-surface-border bg-surface py-2 pl-8 pr-3 text-sm
              placeholder:text-fg-faint focus:outline-none focus:ring-2 focus:ring-primary/40"
          />
        </div>
      </div>

      {isError ? (
        <p className="text-sm text-danger">Falha ao carregar execuções.</p>
      ) : isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-24 w-full" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={JobsIcon}
          title={data?.length ? "Nenhuma execução com esse filtro" : "Nenhuma execução ainda"}
          description="Execute um workflow para criar uma run."
        />
      ) : (
        <div className="space-y-2">
          {filtered.map((j) => (
            <RunCard
              key={j.id}
              job={j}
              pipelineName={wfName.get(j.workflow_id) ?? j.workflow_id.slice(0, 8)}
              runNumber={runNo.get(j.id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
