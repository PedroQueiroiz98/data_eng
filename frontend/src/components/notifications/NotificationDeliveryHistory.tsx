import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  Button,
  Column,
  DataTable,
  Drawer,
  EmptyState,
  SelectField,
  StatusChip,
  TextField,
  useToast,
} from "@/ui";
import { HistoryIcon } from "@/ui/icons";
import {
  useNotificationDeliveries,
  useNotificationProviders,
  useRetryNotificationDelivery,
} from "@/hooks/useNotificationProviders";
import type {
  DeliveryFilters,
  NotificationDelivery,
} from "@/lib/notificationProviders";
import { EVENT_LABEL } from "@/components/notifications/providerMeta";

const STATUSES = ["PENDING", "SENDING", "SENT", "FAILED"] as const;
const EVENTS = ["JOB_FAILED", "WORKFLOW_FAILED"] as const;

interface Props {
  jobFilter?: string;
  workflowFilter?: string;
  /** esconde a barra de filtros (uso embutido, ex.: aba do Job) */
  compact?: boolean;
}

export function NotificationDeliveryHistory({
  jobFilter,
  workflowFilter,
  compact = false,
}: Props) {
  const toast = useToast();
  const providers = useNotificationProviders();
  const retry = useRetryNotificationDelivery();

  const [provider, setProvider] = useState("");
  const [status, setStatus] = useState("");
  const [event, setEvent] = useState("");
  const [environment, setEnvironment] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [selected, setSelected] = useState<NotificationDelivery | null>(null);

  const filters: DeliveryFilters = useMemo(
    () => ({
      job: jobFilter,
      workflow: workflowFilter,
      provider: provider || undefined,
      status: (status || undefined) as DeliveryFilters["status"],
      event: (event || undefined) as DeliveryFilters["event"],
      environment: environment || undefined,
      date_from: dateFrom ? new Date(dateFrom).toISOString() : undefined,
      date_to: dateTo ? new Date(dateTo).toISOString() : undefined,
      limit: 100,
    }),
    [jobFilter, workflowFilter, provider, status, event, environment, dateFrom, dateTo],
  );

  const { data, isLoading, isError } = useNotificationDeliveries(filters);
  const providerName = (id: string | null) =>
    providers.data?.find((p) => p.id === id)?.name;

  const doRetry = (d: NotificationDelivery) =>
    retry.mutate(d.id, {
      onSuccess: () => toast.success("Reenvio enfileirado"),
      onError: (e) => toast.error((e as Error).message),
    });

  const columns: Column<NotificationDelivery>[] = [
    {
      key: "created",
      header: "Data",
      sortValue: (d) => d.created_at,
      render: (d) => (
        <span className="text-xs text-fg-muted">
          {new Date(d.created_at).toLocaleString()}
        </span>
      ),
    },
    {
      key: "provider",
      header: "Provedor",
      render: (d) => providerName(d.notification_provider_id) ?? d.provider_type,
    },
    {
      key: "event",
      header: "Evento",
      render: (d) => EVENT_LABEL[d.event_type] ?? d.event_type,
    },
    {
      key: "scope",
      header: "Escopo",
      render: (d) =>
        d.job_id ? (
          <Link className="text-primary hover:underline" to={`/jobs/${d.job_id}`}>
            Job #{d.job_id.slice(0, 8)}
          </Link>
        ) : (
          <span className="text-fg-faint">—</span>
        ),
    },
    {
      key: "status",
      header: "Status",
      sortValue: (d) => d.status,
      render: (d) => <StatusChip status={d.status} size="sm" />,
    },
    {
      key: "attempt",
      header: "Tentativas",
      render: (d) => (
        <span className="text-xs text-fg-faint">
          {d.attempt}/{d.max_attempts}
        </span>
      ),
    },
    {
      key: "error",
      header: "Erro",
      render: (d) =>
        d.error_message ? (
          <span className="line-clamp-1 max-w-xs text-xs text-danger">
            {d.error_message}
          </span>
        ) : null,
    },
  ];

  return (
    <div className="space-y-3">
      {!compact && (
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        <SelectField
          label="Provedor"
          value={provider}
          onChange={(e) => setProvider(e.target.value)}
        >
          <option value="">Todos</option>
          {providers.data?.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </SelectField>
        <SelectField label="Status" value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">Todos</option>
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </SelectField>
        <SelectField label="Evento" value={event} onChange={(e) => setEvent(e.target.value)}>
          <option value="">Todos</option>
          {EVENTS.map((s) => (
            <option key={s} value={s}>
              {EVENT_LABEL[s]}
            </option>
          ))}
        </SelectField>
        <TextField
          label="Ambiente"
          value={environment}
          onChange={(e) => setEnvironment(e.target.value)}
        />
        <TextField
          label="De"
          type="date"
          value={dateFrom}
          onChange={(e) => setDateFrom(e.target.value)}
        />
        <TextField
          label="Até"
          type="date"
          value={dateTo}
          onChange={(e) => setDateTo(e.target.value)}
        />
      </div>
      )}

      {isError ? (
        <p className="text-sm text-danger">Falha ao carregar o histórico.</p>
      ) : (
        <DataTable
          columns={columns}
          rows={data?.items}
          rowKey={(d) => d.id}
          loading={isLoading}
          onRowClick={(d) => setSelected(d)}
          empty={
            <EmptyState
              icon={HistoryIcon}
              title="Nenhum envio registrado"
              description="Quando um Job ou Workflow falhar, as tentativas de notificação aparecem aqui."
            />
          }
        />
      )}

      <Drawer
        open={!!selected}
        onClose={() => setSelected(null)}
        title="Detalhes da notificação"
        footer={
          selected?.status === "FAILED" ? (
            <Button
              loading={retry.isPending}
              onClick={() => {
                doRetry(selected);
                setSelected(null);
              }}
            >
              Reenviar
            </Button>
          ) : null
        }
      >
        {selected && (
          <dl className="space-y-2 text-sm">
            <Row k="Provedor" v={providerName(selected.notification_provider_id) ?? selected.provider_type} />
            <Row k="Evento" v={EVENT_LABEL[selected.event_type] ?? selected.event_type} />
            <Row k="Status" v={<StatusChip status={selected.status} size="sm" />} />
            <Row k="Tentativa" v={`${selected.attempt}/${selected.max_attempts}`} />
            <Row k="Destinatário" v={selected.recipient ?? "—"} />
            <Row k="Job" v={selected.job_id ?? "—"} />
            <Row k="Workflow" v={selected.workflow_id ?? "—"} />
            <Row k="Execution" v={selected.execution_id ?? "—"} />
            <Row k="Criado" v={new Date(selected.created_at).toLocaleString()} />
            <Row
              k="Enviado"
              v={selected.sent_at ? new Date(selected.sent_at).toLocaleString() : "—"}
            />
            {selected.error_message && (
              <div>
                <dt className="text-xs font-medium text-fg-muted">Erro</dt>
                <pre className="mt-1 overflow-x-auto whitespace-pre-wrap rounded bg-danger/5 px-2 py-1 text-xs text-danger">
                  {selected.error_message}
                </pre>
              </div>
            )}
          </dl>
        )}
      </Drawer>
    </div>
  );
}

function Row({ k, v }: { k: string; v: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-4">
      <dt className="text-fg-muted">{k}</dt>
      <dd className="text-right text-fg">{v}</dd>
    </div>
  );
}
