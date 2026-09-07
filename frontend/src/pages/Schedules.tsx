import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { bulkFailureReport } from "@/components/bulkReport";
import {
  useCreateSchedule,
  useDeleteSchedule,
  useSchedules,
  useUpdateSchedule,
} from "@/hooks/useSchedules";
import { useWorkflows } from "@/hooks/useWorkflows";
import { bulkRun, bulkSuccessMessage } from "@/lib/bulk";
import { runWorkflow } from "@/lib/jobs";
import { deleteSchedule, type Schedule } from "@/lib/schedules";
import {
  buildCron,
  DEFAULT_PARTS,
  describeCron,
  isValidCron,
  type FreqParts,
  type Frequency,
} from "@/lib/cron";
import {
  ActionMenu,
  Button,
  Column,
  DataTable,
  Dialog,
  EmptyState,
  IconButton,
  PageHeader,
  SelectField,
  StatusChip,
  Switch,
  TextField,
  useAlert,
  useConfirm,
  useToast,
} from "@/ui";
import { AddIcon, DeleteIcon, EditIcon, PauseIcon, RunIcon, ScheduleIcon } from "@/ui/icons";

const FREQS: { value: Frequency; label: string }[] = [
  { value: "once", label: "Uma vez" },
  { value: "hourly", label: "De hora em hora" },
  { value: "daily", label: "Diariamente" },
  { value: "weekly", label: "Semanalmente" },
  { value: "monthly", label: "Mensalmente" },
  { value: "custom", label: "Cron personalizado" },
];
const WEEKDAYS = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"];

interface FormState {
  workflowId: string;
  freq: Frequency;
  parts: FreqParts;
  cron: string;
  timezone: string;
  enabled: boolean;
}

function ScheduleFormDialog({
  open,
  onClose,
  initial,
  editing,
  workflows,
  onSubmit,
  saving,
}: {
  open: boolean;
  onClose: () => void;
  initial?: Partial<FormState>;
  editing: boolean;
  workflows: { id: string; name: string }[];
  onSubmit: (s: FormState, addAnother: boolean) => void;
  saving: boolean;
}) {
  const [s, setS] = useState<FormState>({
    workflowId: "",
    freq: "daily",
    parts: { ...DEFAULT_PARTS },
    cron: "0 9 * * *",
    timezone: "America/Sao_Paulo",
    enabled: true,
    ...initial,
  });

  const effectiveCron = s.freq === "custom" ? s.cron : buildCron(s.freq, s.parts);
  const set = (patch: Partial<FormState>) => setS((prev) => ({ ...prev, ...patch }));
  const setPart = (patch: Partial<FreqParts>) =>
    setS((prev) => ({ ...prev, parts: { ...prev.parts, ...patch } }));

  const valid = s.workflowId && isValidCron(effectiveCron);
  const emit = (addAnother: boolean) => onSubmit({ ...s, cron: effectiveCron }, addAnother);

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={editing ? "Editar agendamento" : "Novo agendamento"}
      footer={
        <>
          <Button variant="text" onClick={onClose}>
            Cancelar
          </Button>
          {!editing && (
            <Button
              variant="outlined"
              loading={saving}
              disabled={!valid}
              onClick={() => emit(true)}
            >
              Salvar e adicionar outro
            </Button>
          )}
          <Button loading={saving} disabled={!valid} onClick={() => emit(false)}>
            Salvar
          </Button>
        </>
      }
    >
      <div className="space-y-3">
        <SelectField
          label="Workflow"
          value={s.workflowId}
          onChange={(e) => set({ workflowId: e.target.value })}
        >
          <option value="">Selecione…</option>
          {workflows.map((w) => (
            <option key={w.id} value={w.id}>
              {w.name}
            </option>
          ))}
        </SelectField>

        <SelectField
          label="Frequência"
          value={s.freq}
          onChange={(e) => set({ freq: e.target.value as Frequency })}
        >
          {FREQS.map((f) => (
            <option key={f.value} value={f.value}>
              {f.label}
            </option>
          ))}
        </SelectField>

        {s.freq === "custom" ? (
          <TextField
            label="Expressão cron (5 campos)"
            mono
            value={s.cron}
            onChange={(e) => set({ cron: e.target.value })}
            error={isValidCron(s.cron) ? undefined : "Cron inválido"}
          />
        ) : (
          <div className="grid grid-cols-2 gap-3">
            {s.freq === "hourly" ? (
              <TextField
                label="Minuto"
                type="number"
                min={0}
                max={59}
                value={s.parts.minute}
                onChange={(e) => setPart({ minute: Number(e.target.value) || 0 })}
              />
            ) : (
              <TextField
                label="Horário"
                type="time"
                value={s.parts.time}
                onChange={(e) => setPart({ time: e.target.value })}
              />
            )}
            {s.freq === "weekly" && (
              <SelectField
                label="Dia da semana"
                value={s.parts.weekday}
                onChange={(e) => setPart({ weekday: Number(e.target.value) })}
              >
                {WEEKDAYS.map((d, i) => (
                  <option key={i} value={i}>
                    {d}
                  </option>
                ))}
              </SelectField>
            )}
            {(s.freq === "monthly" || s.freq === "once") && (
              <TextField
                label="Dia do mês"
                type="number"
                min={1}
                max={31}
                value={s.parts.monthday}
                onChange={(e) => setPart({ monthday: Number(e.target.value) || 1 })}
              />
            )}
            {s.freq === "once" && (
              <TextField
                label="Mês"
                type="number"
                min={1}
                max={12}
                value={s.parts.month}
                onChange={(e) => setPart({ month: Number(e.target.value) || 1 })}
              />
            )}
          </div>
        )}

        <div className="rounded-md bg-surface-variant px-3 py-2 text-xs text-fg-muted">
          <span className="font-medium">{describeCron(effectiveCron)}</span>
          <span className="ml-2 font-mono text-fg-faint">→ {effectiveCron}</span>
        </div>

        <TextField
          label="Timezone"
          value={s.timezone}
          onChange={(e) => set({ timezone: e.target.value })}
        />

        <Switch checked={s.enabled} onChange={(v) => set({ enabled: v })} label="Ativo" />
      </div>
    </Dialog>
  );
}

export function Schedules() {
  const navigate = useNavigate();
  const toast = useToast();
  const confirm = useConfirm();
  const alert = useAlert();
  const qc = useQueryClient();
  const { data: schedules, isLoading, isError } = useSchedules();
  const { data: workflows } = useWorkflows();
  const create = useCreateSchedule();
  const update = useUpdateSchedule();
  const remove = useDeleteSchedule();
  const [bulkBusy, setBulkBusy] = useState(false);

  const bulkDelete = async (ids: string[], clear: () => void) => {
    if (
      !(await confirm({
        title: "Excluir agendamentos",
        message: `Excluir ${ids.length} agendamento(s)?`,
        confirmLabel: "Excluir",
        danger: true,
      }))
    )
      return;
    setBulkBusy(true);
    const res = await bulkRun(ids, deleteSchedule);
    setBulkBusy(false);
    await qc.invalidateQueries({ queryKey: ["schedules"] });
    clear();
    if (res.ok > 0) toast.success(bulkSuccessMessage(res.ok, "agendamento"));
    if (res.failed > 0) {
      const label = (id: string) => {
        const s = schedules?.find((x) => x.id === id);
        return s ? `${wfName(s.workflow_id)} · ${s.cron}` : id.slice(0, 8);
      };
      await alert(bulkFailureReport(res, ids.length, "agendamentos", label));
    }
  };

  const [formOpen, setFormOpen] = useState(false);
  const [formNonce, setFormNonce] = useState(0);
  const [keepWorkflowId, setKeepWorkflowId] = useState("");
  const [editing, setEditing] = useState<Schedule | null>(null);
  const [detail, setDetail] = useState<Schedule | null>(null);

  const wfList = workflows ?? [];
  const wfName = (id: string) => wfList.find((w) => w.id === id)?.name ?? id.slice(0, 8);

  const openCreate = () => {
    setEditing(null);
    setKeepWorkflowId("");
    setFormNonce((n) => n + 1);
    setFormOpen(true);
  };
  const openEdit = (s: Schedule) => {
    setDetail(null);
    setEditing(s);
    setFormNonce((n) => n + 1);
    setFormOpen(true);
  };

  const submit = (f: FormState, addAnother: boolean) => {
    if (editing) {
      update.mutate(
        { id: editing.id, cron: f.cron, timezone: f.timezone, enabled: f.enabled },
        {
          onSuccess: () => {
            toast.success("Agendamento atualizado");
            setFormOpen(false);
          },
          onError: (e) => toast.error((e as Error).message),
        },
      );
      return;
    }
    create.mutate(
      { workflow_id: f.workflowId, cron: f.cron, timezone: f.timezone, enabled: f.enabled },
      {
        onSuccess: () => {
          toast.success("Agendamento criado");
          if (addAnother) {
            setKeepWorkflowId(f.workflowId);
            setFormNonce((n) => n + 1); // remonta o form limpo, mantendo o workflow
          } else {
            setFormOpen(false);
          }
        },
        onError: (e) => toast.error((e as Error).message),
      },
    );
  };

  const toggle = (s: Schedule) =>
    update.mutate(
      { id: s.id, enabled: !s.enabled },
      {
        onSuccess: () => toast.success(s.enabled ? "Agendamento pausado" : "Agendamento ativado"),
        onError: (e) => toast.error((e as Error).message),
      },
    );

  const del = async (s: Schedule) => {
    if (
      await confirm({
        title: "Excluir agendamento",
        message: `Excluir o agendamento de "${wfName(s.workflow_id)}"?`,
        confirmLabel: "Excluir",
        danger: true,
      })
    ) {
      remove.mutate(s.id, {
        onSuccess: () => {
          toast.success("Agendamento excluído");
          setDetail(null);
        },
        onError: (e) => toast.error((e as Error).message),
      });
    }
  };

  const runNow = async (s: Schedule) => {
    try {
      const job = await runWorkflow(s.workflow_id, {});
      toast.success("Execução iniciada");
      navigate(`/jobs/${job.id}`);
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  const columns: Column<Schedule>[] = [
    {
      key: "workflow",
      header: "Workflow",
      sortValue: (s) => wfName(s.workflow_id),
      render: (s) => <span className="font-medium text-fg">{wfName(s.workflow_id)}</span>,
    },
    {
      key: "freq",
      header: "Frequência",
      sortValue: (s) => s.cron,
      render: (s) => (
        <div>
          <div className="text-fg">{describeCron(s.cron)}</div>
          <div className="font-mono text-[11px] text-fg-faint">
            {s.cron} · {s.timezone}
          </div>
        </div>
      ),
    },
    {
      key: "next",
      header: "Próxima execução",
      sortValue: (s) => s.next_run_at ?? "",
      render: (s) => (
        <span className="text-fg-muted">
          {s.next_run_at ? new Date(s.next_run_at).toLocaleString() : "—"}
        </span>
      ),
    },
    {
      key: "status",
      header: "Status",
      sortValue: (s) => String(s.enabled),
      render: (s) => <StatusChip status={s.enabled ? "ENABLED" : "DISABLED"} />,
    },
    {
      key: "actions",
      header: "",
      align: "right",
      render: (s) => (
        <div className="flex items-center justify-end gap-0.5">
          <IconButton
            label="Executar agora"
            size="sm"
            icon={<RunIcon className="h-4 w-4" />}
            onClick={(e) => {
              e.stopPropagation();
              void runNow(s);
            }}
          />
          <IconButton
            label="Editar"
            size="sm"
            icon={<EditIcon className="h-4 w-4" />}
            onClick={(e) => {
              e.stopPropagation();
              openEdit(s);
            }}
          />
          <ActionMenu
            items={[
              {
                label: s.enabled ? "Pausar" : "Ativar",
                icon: <PauseIcon className="h-4 w-4" />,
                onClick: () => toggle(s),
              },
              {
                label: "Excluir",
                icon: <DeleteIcon className="h-4 w-4" />,
                danger: true,
                onClick: () => void del(s),
              },
            ]}
          />
        </div>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        title="Agendamentos"
        subtitle="Execuções automáticas de workflows (cron). Um workflow pode ter vários agendamentos."
        actions={
          <Button icon={<AddIcon className="h-4 w-4" />} onClick={openCreate}>
            Novo Agendamento
          </Button>
        }
      />

      {isError ? (
        <p className="text-sm text-danger">Falha ao carregar agendamentos.</p>
      ) : isLoading ? (
        <p className="text-sm text-fg-faint">Carregando…</p>
      ) : (schedules ?? []).length === 0 ? (
        <EmptyState
          icon={ScheduleIcon}
          title="Nenhum agendamento"
          description="Crie um agendamento para executar um workflow automaticamente."
          action={
            <Button icon={<AddIcon className="h-4 w-4" />} onClick={openCreate}>
              Criar Agendamento
            </Button>
          }
        />
      ) : (
        <DataTable
          columns={columns}
          rows={schedules}
          rowKey={(s) => s.id}
          onRowClick={(s) => setDetail(s)}
          searchPlaceholder="Pesquisar agendamentos"
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
        />
      )}

      <Dialog
        open={detail !== null}
        onClose={() => setDetail(null)}
        title="Detalhes do agendamento"
        footer={
          detail && (
            <>
              <Button
                variant="outlined"
                size="sm"
                icon={<PauseIcon className="h-4 w-4" />}
                onClick={() => detail && toggle(detail)}
              >
                {detail.enabled ? "Pausar" : "Ativar"}
              </Button>
              <Button
                variant="outlined"
                size="sm"
                icon={<EditIcon className="h-4 w-4" />}
                onClick={() => detail && openEdit(detail)}
              >
                Editar
              </Button>
              <Button
                size="sm"
                icon={<RunIcon className="h-4 w-4" />}
                onClick={() => detail && runNow(detail)}
              >
                Executar agora
              </Button>
            </>
          )
        }
      >
        {detail && (
          <dl className="space-y-2 text-sm">
            <Row label="Workflow" value={wfName(detail.workflow_id)} />
            <Row label="Frequência" value={describeCron(detail.cron)} />
            <Row label="Cron" value={<code className="font-mono text-xs">{detail.cron}</code>} />
            <Row label="Timezone" value={detail.timezone} />
            <Row
              label="Próxima execução"
              value={detail.next_run_at ? new Date(detail.next_run_at).toLocaleString() : "—"}
            />
            <Row
              label="Última execução"
              value={detail.last_run_at ? new Date(detail.last_run_at).toLocaleString() : "—"}
            />
            <Row
              label="Status"
              value={<StatusChip status={detail.enabled ? "ENABLED" : "DISABLED"} />}
            />
          </dl>
        )}
      </Dialog>

      {formOpen && (
        <ScheduleFormDialog
          key={formNonce}
          open={formOpen}
          onClose={() => setFormOpen(false)}
          editing={editing !== null}
          workflows={wfList}
          saving={create.isPending || update.isPending}
          onSubmit={submit}
          initial={
            editing
              ? {
                  workflowId: editing.workflow_id,
                  freq: "custom",
                  cron: editing.cron,
                  timezone: editing.timezone,
                  enabled: editing.enabled,
                }
              : keepWorkflowId
                ? { workflowId: keepWorkflowId }
                : undefined
          }
        />
      )}
    </div>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-4">
      <dt className="text-fg-faint">{label}</dt>
      <dd className="text-right text-fg">{value}</dd>
    </div>
  );
}
