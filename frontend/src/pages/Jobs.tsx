import { useNavigate } from "react-router-dom";
import { useJobs } from "@/hooks/useJobs";
import type { Job } from "@/lib/jobs";
import { Column, DataTable, EmptyState, PageHeader, StatusChip } from "@/ui";
import { JobsIcon } from "@/ui/icons";

function fmtDuration(ms: number | null): string {
  if (ms == null) return "—";
  const s = Math.round(ms / 1000);
  return s < 60 ? `${s}s` : `${Math.floor(s / 60)}m ${s % 60}s`;
}

export function Jobs() {
  const navigate = useNavigate();
  const { data, isLoading, isError } = useJobs();

  const columns: Column<Job>[] = [
    {
      key: "status",
      header: "Status",
      sortValue: (j) => j.status,
      render: (j) => <StatusChip status={j.status} />,
    },
    {
      key: "id",
      header: "Job",
      sortValue: (j) => j.id,
      render: (j) => <span className="font-mono text-xs text-primary">{j.id.slice(0, 8)}</span>,
    },
    {
      key: "trigger",
      header: "Gatilho",
      sortValue: (j) => j.trigger_type,
      render: (j) => <span className="text-fg-muted">{j.trigger_type}</span>,
    },
    {
      key: "duration",
      header: "Duração",
      sortValue: (j) => j.duration_ms ?? 0,
      render: (j) => <span className="tabular-nums">{fmtDuration(j.duration_ms)}</span>,
    },
    {
      key: "created",
      header: "Criado",
      sortValue: (j) => j.created_at,
      render: (j) => (
        <span className="text-fg-muted">{new Date(j.created_at).toLocaleString()}</span>
      ),
    },
  ];

  return (
    <div>
      <PageHeader title="Jobs" subtitle="Execuções de workflows." />
      {isError ? (
        <p className="text-sm text-danger">Falha ao carregar jobs.</p>
      ) : (
        <DataTable
          columns={columns}
          rows={data}
          rowKey={(j) => j.id}
          loading={isLoading}
          onRowClick={(j) => navigate(`/jobs/${j.id}`)}
          empty={
            <EmptyState
              icon={JobsIcon}
              title="Nenhum job ainda"
              description="Execute um workflow para criar um job."
            />
          }
        />
      )}
    </div>
  );
}
