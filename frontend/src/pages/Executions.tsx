import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { bulkFailureReport } from "@/components/bulkReport";
import { useExecutions } from "@/hooks/useExecutions";
import { bulkRun, bulkSuccessMessage } from "@/lib/bulk";
import {
  cancelExecution,
  canCancel,
  canRetry,
  deleteExecution,
  retryExecution,
  type Execution,
  type ExecutionStatus,
} from "@/lib/executions";
import {
  Button,
  Column,
  DataTable,
  EmptyState,
  IconButton,
  PageHeader,
  SelectField,
  StatusChip,
  useAlert,
  useConfirm,
  useToast,
} from "@/ui";
import { DeleteIcon, HistoryIcon, RetryIcon, StopIcon, ViewIcon } from "@/ui/icons";

const STATUSES: ExecutionStatus[] = [
  "QUEUED",
  "RUNNING",
  "SUCCESS",
  "FAILED",
  "CANCELLED",
  "TIMEOUT",
];

function fmtDuration(ms: number | null): string {
  if (ms == null) return "—";
  const s = ms / 1000;
  if (s < 60) return `${s.toFixed(1)}s`;
  return `${Math.floor(s / 60)}m ${Math.round(s % 60)}s`;
}

export function Executions() {
  const navigate = useNavigate();
  const toast = useToast();
  const confirm = useConfirm();
  const alert = useAlert();
  const qc = useQueryClient();
  const [status, setStatus] = useState<ExecutionStatus | "">("");
  const [bulkBusy, setBulkBusy] = useState(false);
  const { data, isLoading, isError } = useExecutions(status || undefined);

  const refresh = () => qc.invalidateQueries({ queryKey: ["executions"] });

  const [deletingId, setDeletingId] = useState<string | null>(null);

  const doDelete = async (e: Execution) => {
    const running = e.status === "RUNNING" || e.status === "QUEUED";
    if (
      await confirm({
        title: "Excluir execução",
        message: running
          ? `A execução ${e.id.slice(0, 8)} será cancelada e depois excluída.`
          : `Excluir a execução ${e.id.slice(0, 8)} e seus logs?`,
        confirmLabel: running ? "Cancelar e excluir" : "Excluir",
        danger: true,
      })
    ) {
      setDeletingId(e.id);
      try {
        await deleteExecution(e.id);
        toast.success("Execução excluída");
        refresh();
      } catch (err) {
        toast.error((err as Error).message);
      } finally {
        setDeletingId(null);
      }
    }
  };

  const bulkDelete = async (ids: string[], clear: () => void) => {
    if (
      !(await confirm({
        title: "Excluir execuções",
        message: `Excluir ${ids.length} execução(ões) e seus logs? As que estiverem em andamento são canceladas antes; as que pertencem a um job são ignoradas.`,
        confirmLabel: "Excluir",
        danger: true,
      }))
    )
      return;
    setBulkBusy(true);
    const res = await bulkRun(ids, deleteExecution);
    setBulkBusy(false);
    refresh();
    clear();
    if (res.ok > 0) toast.success(bulkSuccessMessage(res.ok, "execução"));
    if (res.failed > 0) await alert(bulkFailureReport(res, ids.length, "execuções", (id) => id.slice(0, 8)));
  };

  const doCancel = async (e: Execution) => {
    if (
      await confirm({
        title: "Cancelar execução",
        message: `Cancelar a execução ${e.id.slice(0, 8)}?`,
        confirmLabel: "Cancelar execução",
        cancelLabel: "Voltar",
        danger: true,
      })
    ) {
      try {
        await cancelExecution(e.id);
        toast.success("Cancelamento solicitado");
        refresh();
      } catch (err) {
        toast.error((err as Error).message);
      }
    }
  };

  const doRetry = async (e: Execution) => {
    try {
      await retryExecution(e.id);
      toast.success("Reexecução enfileirada");
      refresh();
    } catch (err) {
      toast.error((err as Error).message);
    }
  };

  const columns: Column<Execution>[] = [
    {
      key: "status",
      header: "Status",
      sortValue: (e) => e.status,
      render: (e) => (
        <div className="flex items-center gap-2">
          <StatusChip status={e.status} />
          {e.error_code && <span className="text-xs text-danger">{e.error_code}</span>}
        </div>
      ),
    },
    {
      key: "id",
      header: "Execução",
      sortValue: (e) => e.id,
      render: (e) => <span className="font-mono text-xs text-primary">{e.id.slice(0, 8)}</span>,
    },
    {
      key: "attempt",
      header: "Tentativa",
      sortValue: (e) => e.attempt,
      render: (e) => <span className="tabular-nums">#{e.attempt}</span>,
    },
    {
      key: "duration",
      header: "Duração",
      sortValue: (e) => e.duration_ms ?? 0,
      render: (e) => <span className="tabular-nums">{fmtDuration(e.duration_ms)}</span>,
    },
    {
      key: "created",
      header: "Criada",
      sortValue: (e) => e.created_at,
      render: (e) => (
        <span className="text-fg-muted">{new Date(e.created_at).toLocaleString()}</span>
      ),
    },
    {
      key: "actions",
      header: "",
      align: "right",
      render: (e) => (
        <div className="flex items-center justify-end gap-0.5">
          <IconButton
            label="Visualizar"
            size="sm"
            icon={<ViewIcon className="h-4 w-4" />}
            onClick={(ev) => {
              ev.stopPropagation();
              navigate(`/executions/${e.id}`);
            }}
          />
          {canRetry(e.status) && (
            <IconButton
              label="Reexecutar"
              size="sm"
              icon={<RetryIcon className="h-4 w-4" />}
              onClick={(ev) => {
                ev.stopPropagation();
                void doRetry(e);
              }}
            />
          )}
          {canCancel(e.status) && (
            <IconButton
              label="Cancelar"
              size="sm"
              danger
              icon={<StopIcon className="h-4 w-4" />}
              onClick={(ev) => {
                ev.stopPropagation();
                void doCancel(e);
              }}
            />
          )}
          <IconButton
            label={
              e.status === "RUNNING" || e.status === "QUEUED"
                ? "Cancelar e excluir"
                : "Excluir"
            }
            size="sm"
            danger
            disabled={deletingId === e.id}
            icon={<DeleteIcon className="h-4 w-4" />}
            onClick={(ev) => {
              ev.stopPropagation();
              void doDelete(e);
            }}
          />
        </div>
      ),
    },
  ];

  return (
    <div>
      <PageHeader title="Execuções" subtitle="Histórico de execuções de notebook." />

      <div className="mb-4 max-w-xs">
        <SelectField
          label="Status"
          value={status}
          onChange={(e) => setStatus(e.target.value as ExecutionStatus | "")}
        >
          <option value="">Todos</option>
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </SelectField>
      </div>

      {isError ? (
        <p className="text-sm text-danger">Falha ao carregar execuções.</p>
      ) : (
        <DataTable
          columns={columns}
          rows={data}
          rowKey={(e) => e.id}
          loading={isLoading}
          onRowClick={(e) => navigate(`/executions/${e.id}`)}
          selectable
          bulkActions={(ids, clear) => (
            <Button
              size="sm"
              variant="danger"
              loading={bulkBusy}
              icon={<DeleteIcon className="h-4 w-4" />}
              onClick={() => void bulkDelete(ids, clear)}
            >
              Excluir {ids.length}
            </Button>
          )}
          empty={
            <EmptyState
              icon={HistoryIcon}
              title="Nenhuma execução ainda"
              description="Rode um notebook para ver o histórico aqui."
            />
          }
        />
      )}
    </div>
  );
}
